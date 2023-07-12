from odoo import api, fields, models
    
class ShippingMethod(models.Model):
    _name = "sale.shipping.method"
    _description = 'Shipping method'
    
    name = fields.Char(
        string = "Name", 
        required = True
    )