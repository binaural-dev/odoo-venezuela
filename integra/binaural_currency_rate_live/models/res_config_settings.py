from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    can_update_habil_days = fields.Boolean(
        related="company_id.can_update_habil_days", readonly=False
    )
