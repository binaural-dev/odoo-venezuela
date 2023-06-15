from odoo import api, fields, models
    
class TypeCompanyZmart(models.Model):
    _name = "purchase.type.company"
    
    
    name = fields.Char()