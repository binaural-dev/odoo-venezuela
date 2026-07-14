from odoo import fields, models, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_access_button_mf = fields.Boolean(
        related="pos_config_id.access_button_mf", readonly=False
    )
    message_in_head = fields.Boolean(
        related="pos_config_id.message_in_head", readonly=False
    )
