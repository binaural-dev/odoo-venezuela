from odoo import fields, models, api, _


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    iface_fiscal_data_module = fields.Many2one(
        related="pos_config_id.iface_fiscal_data_module", readonly=False
    )
    pos_access_button_mf = fields.Boolean(
        related="pos_config_id.access_button_mf", readonly=False
    )
    message_in_head = fields.Boolean(
        related="pos_config_id.message_in_head", readonly=False
    )
