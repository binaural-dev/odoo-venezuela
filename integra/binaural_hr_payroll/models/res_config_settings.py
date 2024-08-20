from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    compute_payroll_using = fields.Selection(
        related="company_id.compute_payroll_using", readonly=False
    )

    provisions_cron_day = fields.Integer(related="company_id.provisions_cron_day", readonly=False)
    law_base_wage = fields.Float(related="company_id.law_base_wage", readonly=False)

    ivss_wage_treshold = fields.Float(related="company_id.ivss_wage_treshold", readonly=False)

    forced_unemployment_wage_treshold = fields.Float(
        related="company_id.forced_unemployment_wage_treshold", readonly=False
    )
    use_analytic_account_per_departments = fields.Boolean(
        related="company_id.use_analytic_account_per_departments", readonly=False
    )

    # Vacations
    first_year_vacation_days = fields.Integer(
        related="company_id.first_year_vacation_days", readonly=False
    )
    additional_vacation_days_after_first_year = fields.Integer(
        related="company_id.additional_vacation_days_after_first_year", readonly=False
    )
    cc_additional_days = fields.Integer(related="company_id.cc_additional_days", readonly=False)
    cc_bonus_additional_days = fields.Integer(
        related="company_id.cc_bonus_additional_days", readonly=False
    )
    maximum_vacation_days = fields.Integer(
        related="company_id.maximum_vacation_days", readonly=False
    )

    # Profit Sharing
    profit_sharing_type = fields.Selection(related="company_id.profit_sharing_type", readonly=False)
    profit_sharing_days_qty = fields.Integer(
        related="company_id.profit_sharing_days_qty", readonly=False
    )
