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

        self._register_payroll_benefits(benefits=benefits)
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
        self, benefits=(0, 0), interests=(0, 0), benefits_advance=(0, 0)
    ):
        for employee in self:
            payroll_benefits_accumulated = self.env["hr.payroll.benefits.accumulated"]
            benefits_accumulated_params = {
                "employee_id": employee.id,
                "accumulated_benefits": benefits[0],
                "foreign_accumulated_benefits": benefits[1],
                "accumulated_interest": interests[0],
                "foreign_accumulated_interest": interests[1],
                "accumulated_benefits_advance": benefits_advance[0],
                "foreign_accumulated_benefits_advance": benefits_advance[1],
                "date": fields.Date.today(),
            }
            benefits_accumulated = payroll_benefits_accumulated.search(
                [("employee_id", "=", employee.id)]
            )

            if any(benefits_accumulated):
                benefits_to_update = benefits_accumulated[-1]

                benefits_accumulated_params[
                    "accumulated_benefits"
                ] += benefits_to_update.accumulated_benefits
                benefits_accumulated_params[
                    "foreign_accumulated_benefits"
                ] += benefits_to_update.foreign_accumulated_benefits
                benefits_accumulated_params[
                    "accumulated_interest"
                ] += benefits_to_update.accumulated_interest
                benefits_accumulated_params[
                    "foreign_accumulated_interest"
                ] += benefits_to_update.foreign_accumulated_interest
                benefits_accumulated_params[
                    "accumulated_benefits_advance"
                ] += benefits_to_update.accumulated_benefits_advance
                benefits_accumulated_params[
                    "foreign_accumulated_benefits_advance"
                ] += benefits_to_update.foreign_accumulated_benefits_advance

                benefits_to_update.sudo().write(benefits_accumulated_params)
            else:
                payroll_benefits_accumulated.sudo().create(benefits_accumulated_params)
