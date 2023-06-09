from odoo import api, fields, models,_
    
class ProductTemplatePackagingZmart(models.Model):
    _name = "product.template.packaging"
    
    name = fields.Char(string="Name", required=True)