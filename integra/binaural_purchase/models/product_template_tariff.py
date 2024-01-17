from odoo import api, fields, models, _


class ProductTemplateTariff(models.Model):
    _name = "product.template.tariff"
    _description = "Tarifa de Producto"

    name = fields.Char(string="Name", required=True)
