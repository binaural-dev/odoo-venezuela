from odoo import models, fields

class StockPickingBinauralInventario(models.Model):
    _inherit = 'stock.picking'

    transport_number = fields.Char(string="Transport Number")
    name_company = fields.Many2one(string="Company")
    # vl_number = fields.Char(related='purchase_id.vl_number', string="VL Number")