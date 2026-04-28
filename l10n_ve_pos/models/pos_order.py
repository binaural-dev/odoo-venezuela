from odoo import models, fields, api, _

import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    foreign_currency_id = fields.Many2one("res.currency", related="company_id.foreign_currency_id")
    foreign_amount_total = fields.Float(string="Foreign Total", readonly=True, required=True)
    foreign_currency_rate = fields.Float(readonly=True, required=False)

    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        res["foreign_amount_total"] = ui_order.get("foreign_amount_total", 0.0)
        res["foreign_currency_rate"] = ui_order.get("foreign_currency_rate", 0.0)
        return res

    def _payment_fields(self, order, ui_paymentline):
        res = super()._payment_fields(order, ui_paymentline)
        foreign_amount = ui_paymentline.get("foreign_amount", 0.0)
        foreign_rate = ui_paymentline.get("foreign_rate", 0.0)
        amount = ui_paymentline.get("amount", 0.0)

        if not foreign_amount and foreign_rate:
            foreign_amount = amount / foreign_rate

        res["foreign_amount"] = foreign_amount
        res["foreign_rate"] = foreign_rate
        return res

    def _prepare_invoice_vals(self):
        self.ensure_one()
        res = super()._prepare_invoice_vals()
        res.update(
            {
                "foreign_rate": self.config_id.foreign_rate,
                "foreign_inverse_rate": self.config_id.foreign_inverse_rate,
                "manually_set_rate": True,
            }
        )
        return res 

class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    foreign_currency_rate = fields.Float(related="order_id.foreign_currency_rate")
    foreign_price = fields.Float(readonly=True)

    def _prepare_refund_data(self, refund_order, PosOrderLineLot):
        res = super()._prepare_refund_data(refund_order, PosOrderLineLot)
        res.update({"foreign_price": self.foreign_price})
        return res 

    def _export_for_ui(self, orderline):
        res = super()._export_for_ui(orderline)
        res["foreign_price"] = orderline.foreign_price
        res["foreign_currency_rate"] = orderline.foreign_currency_rate
        return res

