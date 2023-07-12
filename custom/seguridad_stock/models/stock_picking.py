from odoo import models, fields,api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    package_qty = fields.Integer(
        "Package Quantity", 
        help = "Quantity of packages used in the picking"
    )
    destiny = fields.Char()
    shipping_method  = fields.Many2one(
        related = "sale_id.shipping_method"
    )