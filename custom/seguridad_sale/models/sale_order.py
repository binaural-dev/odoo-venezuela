from odoo import api, fields, models

class SaleOrder(models.Model):
    _inherit = "sale.order"
    
    shipping_method = fields.Many2one(
        'sale.shipping.method'
    )