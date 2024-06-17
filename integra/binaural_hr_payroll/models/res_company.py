from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    _sql_constraints = [
        (
            "additional_vacation_days_after_first_year",
            "CHECK(additional_vacation_days_after_first_year > 0)",
            "Additional Vacation Days After First Year must be a positive number",
        ),
        (
            "first_year_vacation_days",
            "CHECK(first_year_vacation_days > 0)",
            "First Year Vacation Days must be a positive number",
        ),
        (
            "cc_additional_days",
            "CHECK(cc_additional_days >= 0)",
            "Colective Contract Additional Days must be a positive number",
        ),
        (
            "cc_bonus_additional_days",
            "CHECK(cc_bonus_additional_days >= 0)",
            "Colective Contract Additional Bonus Days must be a positive number",
        ),
        (
            "profit_sharing_days_qty",
            "CHECK(profit_sharing_days_qty >= 0)",
            "Profit Sharing Days Quantity must be a positive number",
        ),
        (
            "provisions_cron_day",
            "CHECK(provisions_cron_day >= 1 AND provisions_cron_day <= 30)",
            "The value of Provisions Cron Day must be between 1 and 30",
        ),
    ]
    compute_payroll_using = fields.Selection(
        [("base_wage", "Base Wage"), ("foreign_wage", "Foreign Wage")], default="base_wage"
    )

    provisions_cron_day = fields.Integer(
        help="Day of the month in which the provisions cron will be runned", default=1
    )
    law_base_wage = fields.Float(digits=(9, 2), default=130.0)

    ivss_wage_treshold = fields.Float(
        digits=(9, 2), help="Maximum wage that can be used for the IVSS deduction", default=5.0
    )

    forced_unemployment_wage_treshold = fields.Float(
        digits=(9, 2),
        help="Maximum wage that can be used for the forced unemployment deduction",
        default=10.0,
    )
    use_analytic_account_per_departments = fields.Boolean()

    # Vacations
    first_year_vacation_days = fields.Integer(default=16)
    additional_vacation_days_after_first_year = fields.Integer(default=1)
    cc_additional_days = fields.Integer(string="Colective Contract Additional Days")
    cc_bonus_additional_days = fields.Integer(
        string="Colective Contract Additional Bonus Days",
    )
    maximum_vacation_days = fields.Integer(default=30)

    # Profit Sharing
    profit_sharing_type = fields.Selection(
        [("last_wage", "Last accrued wage"), ("annual_avg", "Annual wage average")],
        "Profit sharing base",
        default="last_wage",
    )
    profit_sharing_days_qty = fields.Integer(string="Profit Sharing Days Quantity", default=60)
