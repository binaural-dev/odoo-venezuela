from odoo import models, api, exceptions, fields
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
                lambda x: x.state in ["draft", "posted"]
            )
            if len(invoices) > 0:
                record.partner_id.write({"is_solvent": False})
            else:
                record.partner_id.write({"is_solvent": True})

    def write(self, vals):
        res = super().write(vals)
        self.check_solvent_partner()
        return res

    def check_fixed_concept_product(self, invoice_line_ids):
        """Verifica si al menos una línea de factura tiene un producto con fixed_concept en True."""
        invoice_lines = self.env['account.move.line'].browse(invoice_line_ids)
        return any(line.product_id.fixed_concept for line in invoice_lines if line.product_id)


    def check_fee_period_exists(self, partner_id, fee_period):
        _logger.warning("Verificando período de cuota existente...")
        start_of_month = fee_period.replace(day=1)
        end_of_month = start_of_month + relativedelta(months=1, days=-1)

        return (
            self.search_count(
                [
                    ("partner_id", "=", partner_id),
                    ("fee_period", ">=", start_of_month),
                    ("fee_period", "<=", end_of_month),
                    ("state", "in", ["posted"]),
                    ("payment_state", "in", ["paid", "in_payment", "partial"]),
                ]
            )
            > 0
        )

    @api.model
    def create(self, vals):
        partner_id = vals.get("partner_id")
        fee_period = fields.Date.from_string(vals.get("fee_period"))

        if fee_period and self.check_fee_period_exists(partner_id, fee_period) and self.check_fixed_concept_product() :
            raise ValidationError(
                "Ya existe una factura para este socio en el mismo mes del periodo de la cuota."
            )

        res = super(AccountMove, self).create(vals)
        res.partner_id.write({"is_solvent": False})
        return res
