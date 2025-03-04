from odoo import models, fields, api, _

import logging

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    _inherit = "pos.order"

    foreign_currency_id = fields.Many2one("res.currency", related="company_id.currency_foreign_id")
    foreign_amount_total = fields.Float(string="Foreign Total", readonly=True, required=True)
    foreign_currency_rate = fields.Float(readonly=True, required=False)
    sales_order = fields.Many2one('res.users', string='Sales Order', compute='_compute_sales_order', store=True)

    @api.depends('lines.sale_order_origin_id.user_id')
    def _compute_sales_order(self):
        for order in self:
            if order.lines and order.lines.filtered(lambda x: x.sale_order_origin_id.user_id):
                order.sales_order = order.lines.mapped('sale_order_origin_id.user_id')[:1]
            elif order.partner_id.user_id:
                order.sales_order = order.partner_id.user_id
            else:
                order.sales_order = order.user_id
    
    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
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

    def _prepare_invoice_line(self, order_line):
        res = super()._prepare_invoice_line(order_line)
        res["pos_order_line_ids"] = order_line
        return res

class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    foreign_currency_rate = fields.Float(related="order_id.foreign_currency_rate")
    foreign_price = fields.Float(string="Foreign Price", readonly=True)

    def _prepare_refund_data(self, refund_order, PosOrderLineLot):
        res = super()._prepare_refund_data(refund_order, PosOrderLineLot)
        res.update({"foreign_price": self.foreign_price})
        return res 

    def _export_for_ui(self, orderline):
        return {
            'qty': orderline.qty,
            'price_unit': orderline.price_unit,
            'foreign_price': orderline.foreign_price,
            'price_subtotal': orderline.price_subtotal,
            'price_subtotal_incl': orderline.price_subtotal_incl,
            'product_id': orderline.product_id.id,
            'discount': orderline.discount,
            'tax_ids': [[6, False, orderline.tax_ids.mapped(lambda tax: tax.id)]],
            'id': orderline.id,
            'pack_lot_ids': [[0, 0, lot] for lot in orderline.pack_lot_ids.export_for_ui()],
            'customer_note': orderline.customer_note,
            'refunded_qty': orderline.refunded_qty,
            'price_extra': orderline.price_extra,
            'refunded_orderline_id': orderline.refunded_orderline_id,
            'full_product_name': orderline.full_product_name,
        }

