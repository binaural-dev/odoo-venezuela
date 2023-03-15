from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class AccountMoveRetention(models.Model):
    _inherit = "account.move"

    apply_islr_retention = fields.Boolean(
        string="Apply ISLR Retention?",
        default=False,
        track_visibility="onchange",
    )

    islr_voucher_number = fields.Char(
        string="ISLR Voucher Number",
        track_visibility="onchange",
    )

    iva_voucher_number = fields.Char(
        string="IVA Voucher Number",
        track_visibility="onchange",
    )

    retention_islr_line_ids = fields.One2many(
        "account.retention.line",
        "move_id",
        string="ISLR Retention Lines",
        domain=["|", ("retention_id", "=", False), ("retention_id.type_retention", "=", "islr")],
    )

    retention_iva_line_ids = fields.One2many(
        "account.retention.line",
        "move_id",
        string="IVA Retention Lines",
        domain=[("retention_id.type_retention", "=", "iva")],
    )

    generate_iva_retention = fields.Boolean(
        string="Generate IVA Retention?",
        default=False,
        track_visibility="onchange",
    )

    def action_register_payment(self):
        """
        Override the action_register_payment method to add the invoice lines to the payment register.
        """
        res = super().action_register_payment()
        if self.move_type in ["out_invoice", "out_refund", "in_invoice", "in_refund"]:
            res["context"]["default_retention_line_ids"] = (
                self.invoice_line_ids
                if self.invoice_line_ids.filtered(
                    lambda x: x.tax_ids.filtered(lambda y: y.tax_group_id.name == "IVA")
                )
                else False
            )
            res["context"]["default_retention_type"] = self.move_type
        return res

    def action_post(self):
        """
        Override the action_post method to create the retention payment.
        """
        res = super().action_post()
        Retention = self.env["account.retention"]
        for move in self:
            if move.retention_islr_line_ids and move.move_type == "in_invoice":
                self._validate_amount_islr_retention()
                retention = Retention.create_retention(move, ("islr", "in_invoice"))
                line_to_reconcile = retention.payment_ids[0].move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == "liability_payable" and l.debit > 0
                )[0]
                move.islr_voucher_number = retention.number
                move.js_assign_outstanding_line(line_to_reconcile.id)

            if move.retention_islr_line_ids and move.move_type == "in_refund":
                retention = Retention.create_retention(move, ("islr", "in_refund"))
                line_to_reconcile = retention.payment_ids[0].move_id.line_ids.filtered(
                    lambda l: l.account_id.account_type == "liability_payable" and l.credit > 0
                )[0]
                move.islr_voucher_number = retention.number
                move.js_assign_outstanding_line(line_to_reconcile.id)

            if move.generate_iva_retention:
                if not any(move.invoice_line_ids.mapped("tax_ids").filtered(lambda x: x.amount > 0)):
                    raise UserError(_('The invoice "%s"has no tax.'), move.name)
                retention = Retention.create_retention(move, ("iva", move.move_type))
                if move.move_type not in ("in_invoice", "in_refund"):
                    continue
                if move.move_type == "in_invoice":
                    line_to_reconcile = retention.payment_ids[0].move_id.line_ids.filtered(
                        lambda l: l.account_id.account_type == "liability_payable" and l.debit > 0
                    )[0]
                else:
                    line_to_reconcile = retention.payment_ids[0].move_id.line_ids.filtered(
                        lambda l: l.account_id.account_type == "liability_payable" and l.credit > 0
                    )[0]
                move.iva_voucher_number = retention.number
                move.js_assign_outstanding_line(line_to_reconcile.id)
        return res

    def _validate_amount_islr_retention(self):
        for move in self:
            if move.retention_islr_line_ids.invoice_total > move.amount_total:
                raise UserError(
                    _(
                        "The amount of the retention is greater than the total amount of the invoice."
                    )
                )
            if move.retention_islr_line_ids.invoice_total <= 0:
                raise UserError(_("The amount of the retention must be greater than zero."))
            if not move.journal_id.fiscal:
                raise UserError(_("The journal must be fiscal"))
            if not move.partner_id.type_person_id:
                raise UserError(_("The partner must have a type of person"))
