from odoo import fields, models, api

class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.depends('pos_order_count')
    def _compute_invoice_status(self):
        res = super()._compute_invoice_status()
        for order in self:
            if order.pos_order_count > 0:
                order.invoice_status = "invoiced"
        return res


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _get_sale_order_fields(self):
        res = super()._get_sale_order_fields()
        res.append("foreign_subtotal")
        res.append("foreign_price")
        res.append("foreign_rate")
        res.append("foreign_inverse_rate")
        return res 
    
    
