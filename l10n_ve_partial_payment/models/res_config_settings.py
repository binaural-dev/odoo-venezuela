from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    partial_pay_from_outstanding = fields.Boolean(
        related="company_id.partial_pay_from_outstanding",
        readonly=False,
        string="Enable partial application from outstanding payments on invoice",
    )
