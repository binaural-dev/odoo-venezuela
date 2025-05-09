from odoo import models, fields, api, _

import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    foreign_currency_id = fields.Many2one("res.currency", related="company_id.currency_foreign_id")
    foreign_amount_total = fields.Float(string="Foreign Total", readonly=True, required=True)
    foreign_currency_rate = fields.Float(readonly=True, required=False)
    
    def _process_order(self, order, draft, existing_order):
        res = super()._process_order(order, draft, existing_order)
        order = self.browse(res)
        return res

    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        _logger.info("UI ORDER: %s", ui_order)
        res["foreign_amount_total"] = ui_order["foreign_amount_total"]
        res["foreign_currency_rate"] = ui_order["foreign_currency_rate"]
        return res

    def _payment_fields(self, order, ui_paymentline):
        res = super()._payment_fields(order,ui_paymentline)
        res["foreign_amount"] = ui_paymentline["foreign_amount"]
        res["foreign_rate"] = ui_paymentline["foreign_rate"]
        return res

    def _prepare_invoice_vals(self):
        self.ensure_one()
        res = super()._prepare_invoice_vals()
        res.update(
            {
                "foreign_rate": self.foreign_currency_rate,
                "foreign_inverse_rate": self.foreign_currency_rate,
                "manually_set_rate": True,
            }
        )
        return res

    def _export_for_ui(self, order):
        res = super()._export_for_ui(order)
        res["foreign_currency_rate"] = order.foreign_currency_rate
        return res 

    def get_payments_order_refund(self):
        return self.payment_ids.read()

    @api.model
    def _get_invoice_lines_values(self, line_values, pos_order_line):
        res = super()._get_invoice_lines_values(line_values, pos_order_line)
        res["foreign_price"] = pos_order_line.foreign_price
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

