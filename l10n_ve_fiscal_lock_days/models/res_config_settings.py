from odoo import fields, models, _, api


class ResConfigSettingsInherit(models.TransientModel):
    _inherit = "res.config.settings"

    tax_period = fields.Selection(
        [
            ("fortnightly", "Fortnightly"),
            ("monthly", "Monthly"),
        ],
        string="Tax Period",
        related="company_id.tax_period",
        readonly=False,
    )
    lock_date_tax_validation = fields.Boolean(
        string="Validation to Block Invoice Creation",
        related="company_id.lock_date_tax_validation",
        readonly=False,
    )
