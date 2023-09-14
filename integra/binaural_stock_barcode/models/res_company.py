from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    restrict_add_exceeding_quantity = fields.Boolean(default=True)
