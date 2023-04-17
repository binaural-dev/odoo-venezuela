from odoo import  models,fields

class StockQuantBinauralInventario(models.Model):
    _inherit = 'stock.valuation.layer'

    brand_id = fields.Many2one(
        related='product_id.brand_id', 
        string='Brand to product', 
        help='Trademarks related to the product'
    )