from odoo import fields, models

class StockMoveBinauralInventario(models.Model):
	_inherit = 'stock.move'

	brand_id = fields.Many2one(
        related='product_id.brand_id',
        string='Brand to product', 
        help='Trademarks related to the product'
    )