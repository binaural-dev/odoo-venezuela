from odoo import models, fields

class StockPickingBinauralInventario(models.Model):
    _inherit = 'stock.picking'

    shipping_type = fields.Many2one(related='sale_id.shipping_type', string="Shipping type")
    name_company = fields.Many2one(related='sale_id.name_company', string="Company")
    packing_factor = fields.Char()
    
    