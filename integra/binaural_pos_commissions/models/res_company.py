from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    use_image_from_sale_order = fields.Boolean()
