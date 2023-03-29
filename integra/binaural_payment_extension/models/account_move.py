from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError


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

    company_currency_id = fields.Many2one("res.currency", compute="_compute_currency_fields")
    foreign_currency_id = fields.Many2one("res.currency", compute="_compute_currency_fields")
    base_currency_is_vef = fields.Boolean(compute="_compute_currency_fields")

    def _compute_currency_fields(self):
        for retention in self:
            retention.company_currency_id = self.env.company.currency_id.id
            retention.foreign_currency_id = self.env.company.currency_foreign_id.id
            retention.base_currency_is_vef = self.env.company.currency_id == self.env.ref(
                "base.VEF"
            )

    def action_post(self):
        """
        Override the action_post method to create the retention payment.
        """
        res = super().action_post()
        Retention = self.env["account.retention"]
        for move in self:
            if move.retention_islr_line_ids and move.move_type == "in_invoice":
                self._validate_islr_retention()
                retention = Retention.create_retention(move, ("islr", "in_invoice"))
                retention.action_post()

            if move.retention_islr_line_ids and move.move_type == "in_refund":
                self._validate_islr_retention()
                retention = Retention.create_retention(move, ("islr", "in_refund"))
                retention.action_post()

            if move.generate_iva_retention:
                self._validate_iva_retention()
                retention = Retention.create_retention(move, ("iva", move.move_type))
                if move.move_type not in ("in_invoice", "in_refund"):
                    continue
                retention.action_post()
                move.iva_voucher_number = retention.number
        return res

    def _validate_islr_retention(self):
        """
        Validate that the company has a journal for ISLR supplier retention, the partner a type of
        person, the amount of the retention is greater than zero and that the journal of the
        invoice is fiscal, in order for the ISLR retention to be created.
        """
        self.ensure_one()
        if not self.env.company.islr_supplier_retention_journal_id:
            raise UserError(_("The company must have a journal for ISLR supplier retention."))
        islr_retention = self.retention_islr_line_ids
        sum_invoice_amount = sum(islr_retention.mapped("foreign_invoice_amount"))
        if sum_invoice_amount > self.tax_totals["foreign_amount_untaxed"]:
            raise UserError(
                _("The amount of the retention is greater than the total amount of the invoice.")
            )
        if not self.partner_id.type_person_id:
            raise UserError(_("The partner must have a type of person"))
        if sum_invoice_amount <= 0:
            raise UserError(_("The amount of the retention must be greater than zero."))
        if not self.journal_id.fiscal:
            raise UserError(_("The journal must be fiscal"))

    def _validate_iva_retention(self):
        """
        Validate that the company has a journal for IVA supplier retention, the invoice has at
        least one tax and that the journal of the invoice is fiscal, in order for the IVA retention
        to be created.
        """
        self.ensure_one()
        if not self.env.company.iva_supplier_retention_journal_id:
            raise UserError(_("The company must have a journal for IVA supplier retention."))
        if not any(self.invoice_line_ids.mapped("tax_ids").filtered(lambda x: x.amount > 0)):
            raise UserError(_('The invoice "%s"has no tax.'), self.name)
        if not self.journal_id.fiscal:
            raise UserError(_("The journal must be fiscal"))

    def action_register_payment(self):
        """
        Override the action_register_payment method to send the is_out_invoice context to the
        payment wizard.

        This is used to know if the invoice is an outgoing invoice, in order to know if the
        option to create a retention should be displayed in the payment wizard.
        """
        res = super().action_register_payment()
        res["context"]["default_is_out_invoice"] = any(
            self.filtered(lambda i: i.move_type == "out_invoice")
        )
        return res
