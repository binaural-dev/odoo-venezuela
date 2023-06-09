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
    priority = fields.Selection(
        [
            ("high", "High"),
            ("medium", "Medium"),
            ("low", "Low"),
        ],
        default="low",
        store=True,
        required=True
    )
    date_in_store = fields.Date()