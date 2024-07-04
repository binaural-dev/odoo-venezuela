from datetime import date, datetime
from dateutil import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrPayrollBenefit(models.Model):
    _name = "hr.payroll.benefits.accumulated"
    _rec_name = "employee_name"
    _description = "Payroll Benefits Accumulated"

    employee_id = fields.Many2one("hr.employee", required=True)
    employee_name = fields.Char(related="employee_id.name")
    employee_vat = fields.Char(related="employee_id.vat")
    employee_department_id = fields.Many2one("hr.department", related="employee_id.department_id")
    employee_job_id = fields.Many2one("hr.job", related="employee_id.job_id")

    monthly_or_quarterly_accumulated_benefits = fields.Float(string="Monthly/Quarterly Accumulated")
    annual_accumulated_benefits = fields.Float()
    accumulated_benefits = fields.Float(required=True)
    accumulated_benefits_advance = fields.Float()
    available_benefits = fields.Float(compute="_compute_available_benefits")
    available_benefits_to_pay = fields.Float(compute="_compute_available_benefits_to_pay")
    accumulated_interest = fields.Float(required=True)

    foreign_monthly_or_quarterly_accumulated_benefits = fields.Float(
        string="Monthly/Quarterly Foreign Accumulated"
    )
    foreign_annual_accumulated_benefits = fields.Float()
    foreign_accumulated_benefits = fields.Float(required=True)
    foreign_accumulated_benefits_advance = fields.Float()
    foreign_available_benefits = fields.Float(compute="_compute_available_benefits")
    foreign_available_benefits_to_pay = fields.Float(compute="_compute_available_benefits_to_pay")
    foreign_accumulated_interest = fields.Float(required=True)

    date = fields.Date(string="Last Computation Date", required=True)

    type = fields.Selection(
        [
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
        ],
        compute="_compute_type",
    )

    _sql_constraints = [
        (
            "unique_employee_id",
            "UNIQUE(employee_id)",
            _("This employee already has benefits accumulated."),
        ),
    ]

    @api.depends(
        "accumulated_benefits",
        "accumulated_benefits_advance",
        "foreign_accumulated_benefits",
        "foreign_accumulated_benefits_advance",
    )
    def _compute_available_benefits(self):
        for benefit in self.sudo():
            benefit.available_benefits = (
                benefit.accumulated_benefits - benefit.accumulated_benefits_advance
            )
            benefit.foreign_available_benefits = benefit.foreign_accumulated_benefits = (
                benefit.foreign_accumulated_benefits - benefit.foreign_accumulated_benefits_advance
            )

    @api.depends("available_benefits", "foreign_available_benefits")
    def _compute_available_benefits_to_pay(self):
        for benefit in self.sudo():
            benefit.available_benefits_to_pay = (
                benefit.accumulated_benefits * 0.75
            ) - benefit.accumulated_benefits_advance

            benefit.foreign_available_benefits_to_pay = (
                benefit.foreign_accumulated_benefits * 0.75
            ) - benefit.foreign_accumulated_benefits_advance

    def _compute_employee_mixed_monthly_wage(self):
        self.ensure_one()
        employee = self.employee_id
        seniority = employee.get_seniority_months_since_last_seniority_year()

        if seniority == 0:
            employee.mixed_monthly_wage = 0
            return

        months = seniority if seniority < 3 else 3
        moves = self.env["hr.payroll.move"].search(
            [
                ("employee_id", "=", employee.id),
                ("move_type", "=", "salary"),
            ]
        )
        date_from = date.today() + relativedelta.relativedelta(months=-(months))
        moves_in_between_three_months_and_now = moves.filtered(lambda m: m.date > date_from)
        moves_accrued_sum = sum(
            move.total_accrued for move in moves_in_between_three_months_and_now
        )
        employee.mixed_monthly_wage = moves_accrued_sum / months

    @api.depends("employee_id.company_id.benefits_computation_type")
    def _compute_type(self):
        for benefits in self:
            benefits.type = benefits.employee_id.company_id.benefits_computation_type

    @api.model
    def get_monthly_benefits(self):
        """
        Method intended to be called on a scheduled action (ir.cron).

        It cicles through all the employees of each company, and create the record of the monthly
        accumulated benefit for them depending on the values of the configuration of the company.
        """
        companies = self.env["res.company"].search([])
        for company in companies:
            benefits_computation_type = company.benefits_computation_type
            if benefits_computation_type != "monthly":
                return True

            benefits_days = company.benefits_days_per_month
            if not bool(benefits_days):
                raise UserError(
                    _("The benefits days per month are not defined on the configuration.")
                )

            employees = self.env["hr.employee"].search([])
            for employee in employees:
                if not employee.entry_date:
                    continue

                seniority = employee._get_seniority()
                if seniority.months < 1 and seniority.years < 1:
                    continue

                if employee.last_monthly_calculated_benefits:
                    months_diff = relativedelta.relativedelta(
                        fields.Date.today(), employee.last_monthly_calculated_benefits
                    ).months
                    if months_diff < 1:
                        continue

                employee._get_benefits(benefits_days, True)

    @api.model
    def get_quarterly_benefits(self):
        """
        Method intended to be called on a scheduled action (ir.cron).

        It cicles through all the employees of each company, and create the record of the quarterly
        accumulated benefit for them depending on the values of the configuration of the company.
        """
        companies = self.env["res.company"].search([])
        for company in companies:
            benefits_computation_type = company.benefits_computation_type
            if benefits_computation_type != "quarterly":
                return True

            benefits_days = company.benefits_days_per_month * 3
            if not bool(benefits_days):
                raise UserError(
                    _("The benefits days per month are not defined on the configuration.")
                )

            employees = self.env["hr.employee"].search([])
            for employee in employees:
                if not employee.entry_date:
                    continue

                seniority = employee._get_seniority()
                if seniority.months < 3 and seniority.years < 1:
                    continue

                if employee.last_quarterly_calculated_benefits:
                    months_diff = relativedelta.relativedelta(
                        fields.Date.today(), employee.last_quarterly_calculated_benefits
                    ).months
                    if months_diff < 3:
                        continue

                employee._get_benefits(benefits_days, False)

    @api.model
    def get_annual_benefits(self):
        today = datetime.today().date()

        employees = self.env["hr.employee"].search([])
        for employee in employees:
            entry_date = employee.entry_date
            if not entry_date or today.day != entry_date.day or today.month != entry_date.month:
                continue

            days_per_year = employee.company_id.benefits_days_per_year
            if not days_per_year:
                raise UserError(
                    _("The benefits days per month are not defined on the configuration.")
                )

            maximum_of_days = employee.company_id.maximum_benefits_days_per_year
            if not bool(maximum_of_days):
                raise UserError(
                    _("The maximum benefits days per year are not defined on the configuration.")
                )

            seniority = employee._get_seniority_in_years()
            # Annual benefits calculation should start on the second year of the employee.
            if seniority < 2:
                continue

            days_per_employee_years = days_per_year * seniority

            benefits_days = (
                days_per_employee_years
                if days_per_employee_years < maximum_of_days
                else maximum_of_days
            )

            if employee.last_annual_calculated_benefits:
                months_diff = relativedelta.relativedelta(
                    fields.Date.today(), employee.last_quarterly_calculated_benefits
                ).months
                if months_diff < 12:
                    continue

            employee._get_benefits(benefits_days, is_annual=True)

    @api.model
    def get_benefits_interest(self):
        companies = self.env["res.company"].search([])
        for company in companies:
            if company.benefits_interest_computation_type != "internal":
                continue

            interest_rate = company.benefits_interest_monthly_rate
            if not bool(interest_rate):
                raise UserError(
                    _("The benefits interest monthly rate is not defined on the configuration.")
                )
            daily_interest_rate = interest_rate / 30 / 100

            employees = self.env["hr.employee"].search([])
            for employee in employees:
                benefits_accumulated = self.env["hr.payroll.benefits.accumulated"].search(
                    [
                        ("employee_id", "=", employee.id),
                    ]
                )
                if not any(benefits_accumulated):
                    continue
                if employee.last_calculated_benefits_interest == fields.Date.today():
                    continue

                daily_interests = (
                    benefits_accumulated[-1]["available_benefits"] * daily_interest_rate,
                    benefits_accumulated[-1]["foreign_available_benefits"] * daily_interest_rate,
                )
                employee._register_payroll_benefits(interests=daily_interests)

    @api.model
    def get_benefits_for_employee(self, employee_id):
        benefits = self.env["hr.payroll.benefits.accumulated"].search(
            [
                ("employee_id", "=", employee_id),
            ],
            limit=1,
        )
        return benefits

    @api.model
    def get_available_benefits(self, employee_id):
        benefits = self.get_benefits_for_employee(employee_id)
        return benefits.available_benefits

    @api.model
    def get_foreign_available_benefits(self, employee_id):
        benefits = self.get_benefits_for_employee(employee_id)
        return benefits.foreign_available_benefits

    @api.model
    def get_accumulated_interest(self, employee_id):
        benefits = self.get_benefits_for_employee(employee_id)
        return benefits.accumulated_interest
