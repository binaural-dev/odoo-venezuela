from odoo import api, fields, models
    
class CompanyZmart(models.Model):
    _name = "sale.company"
    
    name = fields.Char(
        string = "Name", 
        required = True
    )