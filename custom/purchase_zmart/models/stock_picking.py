from odoo import models, fields

class StockPickingBinauralInventario(models.Model):
    _inherit = 'stock.picking'

    transport_number = fields.Char(related='purchase_id.transport_number', string="Transport Number")
    name_company = fields.Many2one(related='purchase_id.name_company', string="Company")
    vl_number = fields.Char(related='purchase_id.vl_number', string="VL Number")