from odoo import models, fields

class ProductTemplateBinauralInventario(models.Model):
	_inherit = 'product.template'

	warranty = fields.Char()