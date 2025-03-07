from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    apply_igtf = fields.Boolean(
        related="pos_config_id.apply_igtf", readonly=False, default=True
    )
