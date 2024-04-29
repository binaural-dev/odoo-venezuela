from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_use_seller_from_order = fields.Selection(
        related="company_id.use_seller_from_order",
        readonly=False,
    )
