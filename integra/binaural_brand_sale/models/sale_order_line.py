from odoo import fields, models

class SaleOrderLineBinauralVentas(models.Model):
    _inherit = 'sale.order.line'

    brand_id_sale = fields.Many2one(
        related='product_id.brand_id',
        string='Brand to product',
        help='Trademarks related to the product'
    )