from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    benefits_days_per_month = fields.Integer(
        related="company_id.benefits_days_per_month", readonly=False
    )
    benefits_days_per_year = fields.Integer(
        related="company_id.benefits_days_per_year", readonly=False
    )
    maximum_benefits_days_per_year = fields.Integer(
        related="company_id.maximum_benefits_days_per_year", readonly=False
    )
    benefits_interest_computation_type = fields.Selection(
        related="company_id.benefits_interest_computation_type", readonly=False
    )
    benefits_interest_monthly_rate = fields.Float(
        related="company_id.benefits_interest_monthly_rate", readonly=False
    )
    benefits_computation_type = fields.Selection(
        related="company_id.benefits_computation_type", readonly=False
    )
