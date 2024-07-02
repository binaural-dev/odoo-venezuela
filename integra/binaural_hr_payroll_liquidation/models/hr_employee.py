from datetime import date, datetime
from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    last_monthly_calculated_benefits = fields.Date()
    last_quarterly_calculated_benefits = fields.Date()

    def _get_benefits(self, benefits_days, is_monthly=False, is_annual=False):
        self.ensure_one()

        if not self.contract_id:
            return

        integral_daily_wage = self.contract_id.get_integral_daily_wage()
        benefits_payment = integral_daily_wage * benefits_days

        foreign_integral_daily_wage = self.contract_id.get_foreign_integral_daily_wage()
        foreign_benefits_payment = foreign_integral_daily_wage * benefits_days

        benefits = (benefits_payment, foreign_benefits_payment)

        today = datetime.today().date()

        self._register_payroll_benefits(benefits=benefits, is_annual=is_annual)
        benefits_accumulated = self.env["hr.payroll.benefits.accumulated"].search(
            [("employee_id", "=", self.id)],
            limit=1,
        )

        # Creating the register of the detail
        detail_params = {
            "date": today,
            "employee_id": self.id,
            "amount": benefits_payment,
            "accumulated_amount": benefits_accumulated.accumulated_benefits,
            "foreign_amount": foreign_benefits_payment,
            "foreign_accumulated_amount": benefits_accumulated.foreign_accumulated_benefits,
        }
        if is_monthly:
            detail_params["type"] = "monthly"
            self.last_monthly_calculated_benefits = today
        elif not is_annual:
            detail_params["type"] = "quarterly"
            self.last_quarterly_calculated_benefits = today
        else:
            detail_params["type"] = "annual"
        self.env["hr.payroll.benefits.accumulated.detail"].create(detail_params)

    def _register_payroll_benefits(
        self, benefits=(0, 0), interests=(0, 0), benefits_advance=(0, 0), is_annual=False
    ):
        """
        Registers payroll benefits for employees by either updating existing records or creating
        new ones.

        Parameters
        ----------
        benefits : tuple of float
            A tuple containing two values:
                - benefits[0]: The accumulated benefits for the employee.
                - benefits[1]: The foreign accumulated benefits for the employee.
        interests : tuple of float
            A tuple containing two values:
                - interests[0]: The accumulated interest for the employee.
                - interests[1]: The foreign accumulated interest for the employee.
        benefits_advance : tuple of float
            A tuple containing two values:
                - benefits_advance[0]: The accumulated benefits advance for the employee.
                - benefits_advance[1]: The foreign accumulated benefits advance for the employee.
        is_annual : bool
            A flag indicating whether the benefits being computed are annual. If True, annual
            benefits fields are updated; otherwise, monthly or quarterly benefits fields are
            updated.

        Returns
        -------
        None

        Notes
        -----
        The `benefits`, `interests`, and `benefits_advance` arguments should be tuples with two
        elements each.
        The `is_annual` flag determines which set of accumulated benefits fields are updated.

        Examples
        --------
        Register annual payroll benefits for an employee:

        >>> self._register_payroll_benefits(
        >>>     benefits=(1000, 200),
        >>>     interests=(50, 10),
        >>>     is_annual=True
        >>> )
        """
        for employee in self:

            payroll_benefits_accumulated = self.env["hr.payroll.benefits.accumulated"]

            # Prepare base parameters
            benefits_accumulated_params = {
                "employee_id": employee.id,
                "accumulated_benefits": benefits[0],
                "foreign_accumulated_benefits": benefits[1],
                "accumulated_interest": interests[0],
                "foreign_accumulated_interest": interests[1],
                "accumulated_benefits_advance": benefits_advance[0],
                "foreign_accumulated_benefits_advance": benefits_advance[1],
                "date": fields.Date.today(),
                "annual_accumulated_benefits": 0.0,
                "foreign_annual_accumulated_benefits": 0.0,
                "monthly_or_quarterly_accumulated_benefits": 0.0,
                "foreign_monthly_or_quarterly_accumulated_benefits": 0.0,
            }

            # Set the appropriate accumulated benefits
            if is_annual:
                benefits_accumulated_params.update(
                    {
                        "annual_accumulated_benefits": benefits[0],
                        "foreign_annual_accumulated_benefits": benefits[1],
                    }
                )
            else:
                benefits_accumulated_params.update(
                    {
                        "monthly_or_quarterly_accumulated_benefits": benefits[0],
                        "foreign_monthly_or_quarterly_accumulated_benefits": benefits[1],
                    }
                )

            # Find existing accumulated benefits for the employee
            existing_accumulated = payroll_benefits_accumulated.search(
                [("employee_id", "=", employee.id)], limit=1
            )

            if existing_accumulated:
                # Update with existing values
                benefits_accumulated_params.update(
                    {
                        "annual_accumulated_benefits": (
                            benefits_accumulated_params["annual_accumulated_benefits"]
                            + existing_accumulated.annual_accumulated_benefits
                        ),
                        "foreign_annual_accumulated_benefits": (
                            benefits_accumulated_params["foreign_annual_accumulated_benefits"]
                            + existing_accumulated.foreign_annual_accumulated_benefits
                        ),
                        "monthly_or_quarterly_accumulated_benefits": (
                            benefits_accumulated_params["monthly_or_quarterly_accumulated_benefits"]
                            + existing_accumulated.monthly_or_quarterly_accumulated_benefits
                        ),
                        "foreign_monthly_or_quarterly_accumulated_benefits": (
                            benefits_accumulated_params[
                                "foreign_monthly_or_quarterly_accumulated_benefits"
                            ]
                            + existing_accumulated.foreign_monthly_or_quarterly_accumulated_benefits
                        ),
                        "accumulated_benefits": (
                            benefits_accumulated_params["accumulated_benefits"]
                            + existing_accumulated.accumulated_benefits
                        ),
                        "foreign_accumulated_benefits": (
                            benefits_accumulated_params["foreign_accumulated_benefits"]
                            + existing_accumulated.foreign_accumulated_benefits
                        ),
                        "accumulated_interest": (
                            benefits_accumulated_params["accumulated_interest"]
                            + existing_accumulated.accumulated_interest
                        ),
                        "foreign_accumulated_interest": (
                            benefits_accumulated_params["foreign_accumulated_interest"]
                            + existing_accumulated.foreign_accumulated_interest
                        ),
                        "accumulated_benefits_advance": (
                            benefits_accumulated_params["accumulated_benefits_advance"]
                            + existing_accumulated.accumulated_benefits_advance
                        ),
                        "foreign_accumulated_benefits_advance": (
                            benefits_accumulated_params["foreign_accumulated_benefits_advance"]
                            + existing_accumulated.foreign_accumulated_benefits_advance
                        ),
                    }
                )

                # Update the existing record
                existing_accumulated.sudo().write(benefits_accumulated_params)
            else:
                # Create a new record
                payroll_benefits_accumulated.sudo().create(benefits_accumulated_params)

    def get_fractional_vacation_days(self, is_bonus=False):
        """
        Compute the fractional days or bonus days of vacation for the current year.

        If the vacations of the employee had already been paid this year and their departure month
        (or the current one) is less than they entry month, the result will be 0.

        If the days that are gonna be computed are bonus, the total of days to use as a fraction
        are calculated taking into account the first years for the additional days, else we use the
        additional days starting on year 2.

        Parameters
        ----------
        is_bonus : bool
            If the days that are gonna be computed are bonus vacation days.

        Returns
        -------
        float
            The fraction of days or bonus days of the current year.
        """
        self.ensure_one()
        first_day_of_year = date.today().replace(month=1, day=1)
        last_day_of_year = date.today().replace(month=12, day=1)
        vacation_slips_of_current_year = self.env["hr.payroll.move"].search(
            [
                ("employee_id", "=", self.id),
                ("date_to_vacation", ">=", first_day_of_year),
                ("date_to_vacation", "<=", last_day_of_year),
            ],
            order="date desc",
            limit=1,
        )

        if vacation_slips_of_current_year and self.entry_date.month >= (
            self.departure_date.month if self.departure_date else date.today().month
        ):
            return 0

        seniority_years = self._get_seniority_in_years()
        vacation_days = self.company_id.first_year_vacation_days
        additional_vacation_days_per_year = (
            self.company_id.additional_vacation_days_after_first_year
        )
        additional_vacation_days_total = seniority_years * additional_vacation_days_per_year

        # If the days are not the bonus one, the additional days must be added starting year 2 of
        # the employee.
        if not is_bonus:
            additional_vacation_days_total -= additional_vacation_days_per_year

        months_worked_this_year = (
            self.departure_date.month if self.departure_date else date.today().month
        ) - self.entry_date.month

        days_per_month = (additional_vacation_days_total + vacation_days) / 12
        return days_per_month * months_worked_this_year

    def get_benefits_days_total(self):
        """
        Compute the total days of benefits on the current date.

        These are the benefits days per year from the config multiplied by the number of seniority
        years the employee has starting on year 2.

        Returns
        -------
        int
            The number of benefits days of the employee for the current date.
        """
        self.ensure_one()
        benefits_days_per_year_from_year_two = self.company_id.benefits_days_per_year
        seniority = self._get_seniority_in_years()
        if seniority <= 1:
            return 0
        return benefits_days_per_year_from_year_two * (seniority - 1)

    def _get_benefits_days_per_year(self):
        self.ensure_one()
        maximum_benefits_days_per_year = self.company_id.maximum_benefits_days_per_year
        seniority = self._get_seniority()
        years = int(seniority.years)
        if seniority.months >= 6:
            years += 1
        return years * maximum_benefits_days_per_year

    def _get_benefits_per_years_amount(self):
        payroll_moves = self._get_payroll_moves_grouped_by_months_of_a_specific_year()
        salary_type = self.contract_id.salary_type
        total_accrued = 0
        if salary_type == "variable":
            return 0
        days_per_year = self._get_benefits_days_per_year()
        total_accrued = payroll_moves[-1]["total_accrued"]
        amount_per_days = total_accrued / 30
        return amount_per_days * days_per_year

    def _get_benefits_per_years_foreign_amount(self):
        payroll_moves = self._get_payroll_moves_grouped_by_months_of_a_specific_year()
        salary_type = self.contract_id.salary_type
        total_accrued = 0
        if salary_type == "variable":
            return 0
        days_per_year = self._get_benefits_days_per_year()
        total_accrued = payroll_moves[-1]["foreign_total_accrued"]
        amount_per_days = total_accrued / 30
        return amount_per_days * days_per_year
