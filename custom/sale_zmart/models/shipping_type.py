from odoo import api, fields, models
    
class ShippingZmart(models.Model):
    _name = "sale.shipping.type"
    

    name = fields.Char(string="Name", required=True)