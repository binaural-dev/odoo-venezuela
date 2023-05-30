from odoo import api, fields, models

class PurchaseOrderZmart(models.Model):
    _inherit = "purchase.order"
    
    transport_number = fields.Char(string="Transport Number")
    name_company = fields.Many2one('purchase.company', string="Company")
    vl_number = fields.Char(string="VL Number")