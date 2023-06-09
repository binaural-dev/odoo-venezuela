from odoo import api, fields, models

class SaleOrderZmart(models.Model):
    _inherit = "sale.order"
    
    shipping_type = fields.Many2one(
        'sale.shipping.type',
        string="shipping type"
    )
    name_company = fields.Many2one(
        'sale.company', 
        string="Company"
    )