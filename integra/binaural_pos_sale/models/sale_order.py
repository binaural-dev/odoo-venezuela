from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order.line"

    def _get_sale_order_fields(self):
        res = super()._get_sale_order_fields()
        res.append("foreign_subtotal")
        res.append("foreign_price")
        return res 
