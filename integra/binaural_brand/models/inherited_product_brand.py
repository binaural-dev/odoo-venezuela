from odoo import fields, models

class AccountMoveBrandProduct(models.Model):
    _inherit = 'account.move.line'

    brand_id = fields.Many2one(
        related='product_id.brand_id', 
        string='Brand to product', 
        help='Trademarks related to the product'
    )