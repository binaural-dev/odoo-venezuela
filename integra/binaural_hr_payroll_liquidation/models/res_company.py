from odoo import api, fields, models, _


class ResCompany(models.Model):
    _inherit = "res.company"

    _sql_constraints = [
        (
            "benefits_days_per_month",
            "CHECK(benefits_days_per_month >= 0)",
            "Benefits Days Per Month must be a positive number",
        ),
        (
            "benefits_days_per_year",
            "CHECK(benefits_days_per_year >= 0)",
            "Benefits Days Per Year must be a postitive number",
        ),
        (
            "maximum_benefits_days_per_year",
            "CHECK(maximum_benefits_days_per_year >= 0)",
            "Maximum Benefits Days Per Year must be a positive number",
        ),
    ]

    benefits_days_per_month = fields.Integer(default=5)
    benefits_days_per_year = fields.Integer(default=2)
    maximum_benefits_days_per_year = fields.Integer(default=30)
    benefits_interest_computation_type = fields.Selection(
        [("escrow", "Escrow"), ("internal", "Internal")],
        help="Whether the benefits interest is computed internally or by escrow",
        default="escrow",
    )
    benefits_interest_monthly_rate = fields.Float()
    benefits_computation_type = fields.Selection(
        [("monthly", "Monthly"), ("quarterly", "Quarterly")], default="monthly"
    )
