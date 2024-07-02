from odoo import models, api, exceptions, fields, _
from dateutil.relativedelta import relativedelta
from odoo.exceptions import ValidationError
import datetime
import logging

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    action_number = fields.Char(related="partner_id.action_number.number", readonly=True)

    fee_period = fields.Date(string="Periodo de la cuota")

    pay_soon = fields.Boolean(string="Pronto Pago")

    def check_solvent_partner(self):
        for record in self:
            invoices = record.partner_id.invoice_ids.filtered(
                lambda x: x.payment_state in ["not_paid", "partial"]
                and x.move_type == "out_invoice"
            )
            if len(invoices) > 0:
                record.partner_id.write({"is_solvent": False})
            else:
                record.partner_id.write({"is_solvent": True})

    def js_assign_outstanding_line(self, line_id):
        res = super().js_assign_outstanding_line(line_id)
        self.check_solvent_partner()
        return res

    def js_remove_outstanding_partial(self, partial_id):
        res = super().js_remove_outstanding_partial(partial_id)
        self.check_solvent_partner()
        return res

    def write(self, vals):
        res = super().write(vals)
        self.check_solvent_partner()
        return res

    def check_fee_period_exists(self, partner_id, fee_period, current_invoice_product_ids):
        start_of_month = fee_period.replace(day=1)
        end_of_month = start_of_month + relativedelta(months=1, days=-1)

        existing_invoices = self.search(
            [
                ("partner_id", "=", partner_id),
                ("fee_period", ">=", start_of_month),
                ("fee_period", "<=", end_of_month),
                ("state", "in", ["posted"]),
                ("move_type", "=", "out_invoice"),
                ("payment_state", "not in", ["reversed"]),
            ]
        )

        for invoice in existing_invoices:
            fixed_concept_product_ids = {
                line.product_id.id
                for line in invoice.invoice_line_ids
                if line.product_id and line.product_id.fixed_concept
            }

            if fixed_concept_product_ids.intersection(set(current_invoice_product_ids)):
                return True
        return False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            _logger.warning("Vals: %s", vals)
            _logger.warning("Vals lines: %s", vals.get("invoice_line_ids", []))
            partner_id = vals.get("partner_id")
            fee_period = fields.Date.from_string(vals.get("fee_period"))

            current_invoice_product_ids = [
                line[2]["product_id"]
                for line in vals.get("invoice_line_ids", [])
                if line[2].get("product_id")
            ]

            if fee_period and self.check_fee_period_exists(
                partner_id, fee_period, current_invoice_product_ids
            ):
                raise ValidationError(_("the concept has already been invoiced for this period."))

        moves = super().create(vals_list)
        for move in moves:
            move.partner_id.write({"is_solvent": False})
        return moves

    def action_post(self):
        for record in self:
            if record.move_type == "out_invoice":
                current_invoice_product_ids = [
                    line.product_id.id
                    for line in record.invoice_line_ids
                    if line.product_id and line.product_id.fixed_concept
                ]

                if record.fee_period and self.check_fee_period_exists(
                    record.partner_id.id, record.fee_period, current_invoice_product_ids
                ):
                    raise ValidationError(
                        _("the concept has already been invoiced for this period.")
                    )

        return super(AccountMove, self).action_post()
