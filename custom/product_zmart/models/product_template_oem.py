from odoo import api, fields, models,_
from odoo.exceptions import ValidationError


class ProductTemplateOemZmart(models.Model):
    _name = "product.template.oem"
    
    name = fields.Char(
        string = "OEM", 
        required = True,
        store = True
        )
    
    @api.constrains('name')
    def constraint_unique_name(self):
        for record in self:
            x = self.search([
                ('name', '=', record.name),
                ('id', '!=', record.id)
            ])
            if any(x):
                raise ValidationError(
                    "El nombre ya se encuentra registrado")
                
    @api.constrains('code')
    def constraint_unique_codigo(self):
        for record in self:
            x = self.search([
                ('code', '=', record.code),
                ('id', '!=', record.id)
            ])
            if any(x):
                raise ValidationError(
                    "El codigo ya se encuentra registrado")