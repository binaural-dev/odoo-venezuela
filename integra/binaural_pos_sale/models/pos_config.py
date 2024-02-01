from odoo import fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    pos_use_rate_from_order = fields.Boolean(
        related="company_id.pos_use_rate_from_order", readonly=False
    )
