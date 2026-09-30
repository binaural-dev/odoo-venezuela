from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_self_ordering_hide_catalog = fields.Boolean(
        related="pos_config_id.self_ordering_hide_catalog",
        readonly=False,
    )
