from odoo import models, fields
import logging
_logger = logging.getLogger(__name__)
class StockPickingBinauralInventario(models.Model):
    _inherit = 'stock.picking'

    shipping_type = fields.Selection(related='sale_id.shipping_type', string="Shipping type")
    name_company = fields.Many2one(related='sale_id.name_company', string="Company")
    packing_factor = fields.Char(store="True")
    sequence_code = fields.Char(related='picking_type_id.sequence_code')