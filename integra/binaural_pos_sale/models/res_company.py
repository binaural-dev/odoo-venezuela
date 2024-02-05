from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    pos_use_rate_from_order = fields.Boolean(default=True)
