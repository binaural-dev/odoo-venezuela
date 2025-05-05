from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    use_subsidiary_with_multiple_municipalities = fields.Boolean(
        related="company_id.use_subsidiary_with_multiple_municipalities", readonly=False
    )
