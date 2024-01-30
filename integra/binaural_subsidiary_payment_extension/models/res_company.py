from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    use_subsidiary_with_multiple_municipalities = fields.Boolean()
