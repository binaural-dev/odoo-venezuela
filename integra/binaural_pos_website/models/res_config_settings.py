from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_only_website = fields.Boolean(related="pos_config_id.only_website", readonly=False)
