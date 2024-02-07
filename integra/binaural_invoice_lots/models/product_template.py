from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = "product.template"

    fixed_concept = fields.Boolean(string="Fixed_concept")