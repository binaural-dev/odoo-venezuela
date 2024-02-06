from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_use_rate_from_order = fields.Boolean(
        related="company_id.pos_use_rate_from_order", readonly=False
    )
