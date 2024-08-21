from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_use_image_from_sale_order = fields.Boolean(
        related="company_id.use_image_from_sale_order", readonly=False
    )
