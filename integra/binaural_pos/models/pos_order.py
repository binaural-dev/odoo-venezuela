from odoo import models, fields, api, _

import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    foreign_currency_id = fields.Many2one("res.currency", related="company_id.currency_foreign_id")
    foreign_amount_total = fields.Float(string="Foreign Total", readonly=True, required=True)
    foreign_currency_rate = fields.Float(readonly=True, required=True)
    to_receipt = fields.Boolean(readonly=True)

    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        res["foreign_amount_total"] = ui_order["foreign_amount_total"]
        res["foreign_currency_rate"] = ui_order["foreign_currency_rate"]
        res["to_receipt"] = ui_order["to_receipt"]
        return res

    def _payment_fields(self, order, ui_paymentline):
        res = super()._payment_fields(order,ui_paymentline)
        res["foreign_amount"] = ui_paymentline["foreign_amount"]
        res["foreign_rate"] = ui_paymentline["foreign_rate"]
        return res

    def _prepare_invoice_vals(self):
        self.ensure_one()
        res = super()._prepare_invoice_vals()
        if not self.to_receipt:
            return res
        res.update({"journal_id": self.session_id.config_id.receipt_journal_id.id})
        return res

    def _export_for_ui(self, order):
        res = super()._export_for_ui(order)
        res["foreign_currency_rate"] = order.foreign_currency_rate
        return res 

    def get_payments_order_refund(self):
        return self.payment_ids.read()

class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    foreign_currency_rate = fields.Float(related="order_id.foreign_currency_rate")

