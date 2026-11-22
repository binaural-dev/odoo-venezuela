from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    show_rate_systray = fields.Boolean(
        related="company_id.show_rate_systray",
        readonly=False,
    )
    rate_systray_currency_id = fields.Many2one(
        related="company_id.rate_systray_currency_id",
        readonly=False,
    )
