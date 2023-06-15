from odoo import api, fields, models
    
class IcotermCompanyZmart(models.Model):
    _name = "purchase.icoterm"
    
    name = fields.Char(required=True)