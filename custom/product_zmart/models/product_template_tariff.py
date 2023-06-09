from odoo import api, fields, models,_
    
class ProductTemplateTariffZmart(models.Model):
    _name = "product.template.tariff"
    
    name = fields.Char(string="Name", required=True)