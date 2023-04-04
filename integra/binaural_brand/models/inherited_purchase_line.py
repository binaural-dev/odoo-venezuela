from odoo import  fields, models

class PurchaseOrderLineBinauralCompras(models.Model):
    _inherit = 'purchase.order.line'

    brand_id_purchase = fields.Many2one(
        related='product_id.brand_id', 
        string='Brand to product',
        help='Trademarks related to the product'
    )