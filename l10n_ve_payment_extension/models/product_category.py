from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    ciu_id = fields.Many2one("economic.activity", string="CIU")
