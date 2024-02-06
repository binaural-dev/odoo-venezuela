from dateutil import relativedelta
from math import floor

from odoo import api, fields, models, _


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

    entry_date = fields.Date(required=True, tracking=True)
    seniority = fields.Char(compute="_compute_seniority")

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

        return relativedelta.relativedelta(to_date, from_date)

    def get_all_payroll_moves(self):
        self._cr.execute(
            """
                SELECT
                    EXTRACT(MONTH FROM date) AS month,
                    SUM(total_basic) as total_basic,
                    SUM(total_accrued) as total_accrued
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

    def get_vacation_bonus_days_alicuot(self):
        self.ensure_one()
        vacation_bonus_days = self.get_vacation_bonus_days()
        moves = self.get_all_payroll_moves()
        return (vacation_bonus_days / 360) * (moves[-1]["total_accrued"] / 30)

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
