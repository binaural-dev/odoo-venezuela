from dateutil.relativedelta import relativedelta
from datetime import date, datetime
from math import ceil, floor

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    prefix_vat = fields.Selection(
        [
            ("V", "V"),
            ("E", "E"),
        ],
        default="V",
    )
    vat = fields.Char(string="ID")
    vat_rif = fields.Char(string="RIF")

    porc_ari = fields.Float(
        string="ARI Percentage",
        help="ISLR Retention Percentage",
        digits=(5, 2),
        default=0.0,
    )
    no_ivss = fields.Boolean(string="Does not quote IVSS")
    no_faov = fields.Boolean(string="Does not quote FAOV")
    no_pmpf = fields.Boolean(string="Does not quote forced unemployment")

    entry_date = fields.Date(tracking=True)
    seniority = fields.Char(compute="_compute_seniority")

    allowance_line_ids = fields.One2many(
        "hr.allowance.line", "employee_id", string="Salary Allowances", tracking=True
    )

    holidays_accrued = fields.Float(compute="_compute_holidays_accrued")
    foreign_holidays_accrued = fields.Float(compute="_compute_holidays_accrued")

    @api.depends("entry_date", "departure_date")
    def _compute_seniority(self):
        for employee in self:
            seniority = ""
            diff = self._get_seniority()
            if diff:
                years = diff.years
                months = diff.months
                days = diff.days

                years_string = _("Years") if years > 1 else _("Year")
                months_string = _("Months") if months > 1 else _("Month")
                days_string = _("Days") if days > 1 else _("Day")

                if days > 0:
                    seniority += f"{days} {days_string}"
                if months > 0 and days > 0:
                    seniority = f"{months} {months_string} / " + seniority
                elif months > 0:
                    seniority = f"{months} {months_string} " + seniority
                if years > 0 and (days > 0 or months > 0):
                    seniority = f"{years} {years_string} / " + seniority
                elif years > 0:
                    seniority = f"{years} {years_string} " + seniority
            employee.seniority = seniority

    def _get_seniority(self):
        self.ensure_one()

        if not self.entry_date:
            return None

        from_date = self.entry_date
        to_date = self.departure_date if self.departure_date else fields.Date.today()

        return relativedelta(to_date, from_date)

    @api.depends("contract_id")
    def _compute_holidays_accrued(self):
        for employee in self:
            employee.holidays_accrued = 0
            employee.foreign_holidays_accrued = 0
            if not employee.contract_id:
                continue
            salary_type = employee.contract_id.salary_type
            employee_salary_payments = employee.get_all_payroll_moves()

            if salary_type and employee_salary_payments:
                last_month_payment = employee_salary_payments[-1]
                if salary_type == "fixed":
                    employee.holidays_accrued = last_month_payment["total_accrued"]
                    employee.foreign_holidays_accrued = last_month_payment["foreign_total_accrued"]
                    continue

                last_month_accrued = (
                    last_month_payment["total_accrued"],
                    last_month_payment["foreign_total_accrued"],
                )
                second_to_last_month_accrued = (
                    (
                        employee_salary_payments[-2]["total_accrued"],
                        employee_salary_payments[-2]["foreign_total_accrued"],
                    )
                    if len(employee_salary_payments) > 1
                    else (0, 0)
                )
                third_to_last_month_accrued = (
                    (
                        employee_salary_payments[-3]["total_accrued"],
                        employee_salary_payments[-3]["foreign_total_accrued"],
                    )
                    if len(employee_salary_payments) > 2
                    else (0, 0)
                )

                employee.holidays_accrued = (
                    last_month_accrued[0]
                    + second_to_last_month_accrued[0]
                    + third_to_last_month_accrued[0]
                ) / 3
                employee.foreign_holidays_accrued = (
                    last_month_accrued[1]
                    + second_to_last_month_accrued[1]
                    + third_to_last_month_accrued[1]
                ) / 3

    def get_vacation_bonus_days_alicuot(self):
        self.ensure_one()
        vacation_bonus_days = self.get_vacation_bonus_days()
        moves = self.get_all_payroll_moves()
        return (vacation_bonus_days / 360) * (moves[-1]["total_accrued"] / 30)

    def get_foreign_vacation_bonus_days_alicuot(self):
        self.ensure_one()
        vacation_bonus_days = self.get_vacation_bonus_days()
        moves = self.get_all_payroll_moves()
        return (vacation_bonus_days / 360) * (moves[-1]["foreign_total_accrued"] / 30)

    def get_vacation_bonus_days(self):
        self.ensure_one()
        seniority_in_months = self.get_seniority_in_months()
        additional_days = self.company_id.additional_vacation_days_after_first_year
        annual_vacation_days = self.company_id.first_year_vacation_days
        maximum_vacation_days = self.company_id.maximum_vacation_days
        cc_additional_days = self.company_id.cc_additional_days
        vacation_bonus_days = (
            (floor(seniority_in_months / 12.0) * additional_days)
            + annual_vacation_days
            + cc_additional_days
        )
        return (
            vacation_bonus_days
            if vacation_bonus_days < maximum_vacation_days
            else maximum_vacation_days
        )

    def get_seniority_in_months(self):
        self.ensure_one()
        seniority = self._get_seniority()
        if not seniority:
            return 0
        return seniority.years * 12 + seniority.months

    def get_profit_sharing_days_alicuot(self):
        self.ensure_one()
        profit_sharing_days = self.company_id.profit_sharing_days_qty
        moves = self.get_all_payroll_moves()
        return (profit_sharing_days / 360) * (moves[-1]["total_accrued"] / 30)

    def get_foreign_profit_sharing_days_alicuot(self):
        self.ensure_one()
        profit_sharing_days = self.company_id.profit_sharing_days_qty
        moves = self.get_all_payroll_moves()
        return (profit_sharing_days / 360) * (moves[-1]["foreign_total_accrued"] / 30)

    def get_all_payroll_moves(self):
        self._cr.execute(
            """
                SELECT
                    EXTRACT(MONTH FROM date) AS month,
                    SUM(total_basic) as total_basic,
                    SUM(total_accrued) as total_accrued,
                    SUM(foreign_total_basic) as foreign_total_basic,
                    SUM(foreign_total_accrued) as foreign_total_accrued
                FROM hr_payroll_move as move
                WHERE
                    employee_id = %s AND
                    move_type = 'salary'
                GROUP BY month
                ORDER BY month asc;
            """,
            (self.id,),
        )
        moves = self._cr.dictfetchall()
        return moves

    def get_profit_sharing_wage(self):
        self.ensure_one()
        if self.company_id.profit_sharing_type == "annual_avg":
            return self._get_average_wage() / 30

        moves = self.get_all_payroll_moves()
        if not moves:
            raise UserError(_("There are no payslips for the employee: %s", self.name))
        return moves[-1]["total_accrued"] / 30

    def get_foreign_profit_sharing_wage(self):
        self.ensure_one()
        if self.company_id.profit_sharing_type == "annual_avg":
            return self._get_average_wage(True) / 30

        moves = self.get_all_payroll_moves()
        if not moves:
            raise UserError(_("There are no payslips for the employee: %s", self.name))
        return moves[-1]["foreign_total_accrued"] / 30

    def _get_average_wage(self, get_foreign=False):
        self.ensure_one()
        moves = self._get_payroll_moves_grouped_by_months_of_a_specific_year()
        if not moves:
            return 0

        last_month = int(moves[-1]["month"])
        last_month_wage = moves[-1]["total_accrued"]
        last_month_foreign_wage = moves[-1]["foreign_total_accrued"]
        for month in range(last_month + 1, 13):
            moves.append(
                {
                    "month": month,
                    "total_accrued": last_month_wage,
                    "foreign_total_accrued": last_month_foreign_wage,
                }
            )
        if get_foreign:
            annual_average = sum(move["foreign_total_accrued"] for move in moves) / len(moves)
        else:
            annual_average = sum(move["total_accrued"] for move in moves) / len(moves)

        return annual_average

    def _get_payroll_moves_grouped_by_months_of_a_specific_year(self, year=datetime.today().year):
        self.ensure_one()
        self._cr.execute(
            """
                SELECT
                    EXTRACT(MONTH FROM date) AS month,
                    SUM(total_basic) as total_basic,
                    SUM(total_accrued) as total_accrued,
                    SUM(foreign_total_basic) as foreign_total_basic,
                    SUM(foreign_total_accrued) as foreign_total_accrued
                FROM hr_payroll_move as move
                WHERE
                    employee_id = %s AND
                    move_type = 'salary' AND
                    EXTRACT(YEAR FROM date) = %s
                GROUP BY month
                ORDER BY month asc;
            """,
            (self.id, year),
        )
        return self._cr.dictfetchall()

    def get_profit_sharing_days(self, liquidation=False) -> int:
        self.ensure_one()
        profit_sharing_days_conf = self.company_id.profit_sharing_days_qty
        seniority_in_years = self._get_seniority_in_years()

        if seniority_in_years >= 1 and not liquidation:
            return profit_sharing_days_conf

        seniority_in_months = self.get_seniority_months_since_first_day_of_year()
        return ceil(profit_sharing_days_conf / 12 * seniority_in_months)

    def _get_seniority_in_years(self):
        self.ensure_one()
        seniority = 0
        if self.entry_date:
            from_date = self.entry_date
            to_date = self.departure_date if self.departure_date else fields.Date.today()

            diff = relativedelta(to_date, from_date)
            seniority = diff.years
        return seniority

    def get_seniority_months_since_first_day_of_year(self):
        self.ensure_one()
        seniority = self._get_seniority()
        if seniority is None:
            return 0
        first_day_of_year = date.today().replace(month=1, day=1)
        if self.entry_date >= first_day_of_year:
            return self.get_seniority_in_months()
        seniority_in_months = relativedelta(datetime.today(), first_day_of_year).months
        return seniority_in_months

    def _get_vacation_bonus_days_of_previous_moves(self):
        self.ensure_one()
        vacation_moves = self.env["hr.payroll.move"].search(
            [
                ("employee_id", "=", self.id),
                # ("move_type", "=", "vacation"),
            ]
        )
        result = sum(move.vacation_bonus_days for move in vacation_moves)
        return result

    def _has_paid_vacation(self, year=datetime.today().year):
        first_day_of_year = date(year, 1, 1)
        last_day_of_year = date(year, 12, 31)

        vacation_moves = self.env["hr.payroll.move"].search(
            [
                ("employee_id", "=", self.id),
                ("move_type", "=", "vacation"),
                ("date", ">=", first_day_of_year),
                ("date", "<=", last_day_of_year),
            ]
        )

        return any(vacation_moves)

    def get_not_paid_vacation_bonus_days(self):
        """
        Compute the number of bonus days of the previous years that had not been paid (without
        taking into account the fraction of the current year).

        Those are, the number of bonus days that correspond to the employee on all history minus
        the bonus days on the payroll moves of type vacation that the they have.

        Returns
        -------
        int
            The number of bonus days not paid.
        """
        self.ensure_one()
        seniority_years = self._get_seniority_in_years()
        if seniority_years == 0:
            return 0

        additional_days = self.company_id.additional_vacation_days_after_first_year
        annual_vacation_bonus_days = self.company_id.first_year_vacation_days + 1
        bonus_days_of_the_current_year = annual_vacation_bonus_days + (
            seniority_years * additional_days
        )

        vacation_slips = self.env["hr.payroll.move"].search(
            [
                ("employee_id", "=", self.id),
                # ("move_type", "=", "vacation"),
            ]
        )
        bonus_days_taken = sum(slip.vacation_bonus_days for slip in vacation_slips)

        total_employee_bonus_days = sum(
            range(annual_vacation_bonus_days, bonus_days_of_the_current_year)
        )
        return total_employee_bonus_days - bonus_days_taken

    def get_fractional_vacation_days(self, is_bonus=False):
        """
        Compute the fractional days or bonus days of vacation for the current year.

        If the vacations of the employee had already been paid this year and they departure month
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
            self.departure_date.month if self.departure_date else date.today.month
        ):
            return 0

        seniority_years = self._get_seniority_in_years()
        vacation_days = self.company_id.first_year_vacation_day
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
