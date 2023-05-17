from odoo import models, fields, api


class Brand(models.Model):
    _name = "product.brand"
    _description = "Brands"
    _check_company_auto = True

    active = fields.Boolean(default=True)
    name = fields.Char(required=True, help="Brand name")
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company.id)
