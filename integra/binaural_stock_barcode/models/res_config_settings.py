from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    create_invoice_after_validate_out = fields.Boolean(
        related="company_id.create_invoice_after_validate_out", readonly=False
    )
