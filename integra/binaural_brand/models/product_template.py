from odoo import models, fields

class ProductTemplateBinauralInventario(models.Model):
	_inherit = 'product.template'

	brand_id = fields.Many2one(
        'product.brand',
		string='Brand to product',
		help='Trademarks related to the product'
    )