from odoo import api, fields, models
    
class AduanaZmart(models.Model):
    _name = "purchase.aduana.agent"
    
    name = fields.Char(
        string="Name", 
        required=True
    )