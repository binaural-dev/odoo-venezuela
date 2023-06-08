from odoo import api, fields, models
    
class SaleAreaZmart(models.Model):
    _name = "res.partner.sale"
    
    name_area = fields.Char(string="Area")
    name = fields.Char(string="Name", required=True)