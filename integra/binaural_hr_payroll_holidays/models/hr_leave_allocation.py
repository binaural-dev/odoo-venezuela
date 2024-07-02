from odoo import _, api, fields, models


class HrLeaveAllocation(models.Model):
    _inherit = "hr.leave.allocation"

    @api.model
    def create_vacation_allocation_per_employee(self):
        """
        Creates a leave allocation of type vacation for each employee that has one year or more and
        its entry day and month correspond with the current ones with the corresponding number of
        days based on their seniority.
        """
        vacation_leave_type_id = self.env["ir.model.data"]._xmlid_to_res_id(
            "hr_holidays.holiday_status_cl"
        )
        HrEmployee = self.env["hr.employee"]
        employees_with_one_year_of_seniority_or_more = (
            HrEmployee.get_employees_having_entry_date_month_and_day()
        )

        for employee in employees_with_one_year_of_seniority_or_more:
            company_id = employee.company_id
            vacation_days = (
                company_id.first_year_vacation_days
                + company_id.cc_additional_days
                + (
                    company_id.additional_vacation_days_after_first_year
                    * (employee._get_seniority_in_years() - 1)
                )
            )
            vacation_allocation = self.create(
                {
                    "name": _("Vacation Allocation"),
                    "holiday_type": "employee",
                    "employee_id": employee.id,
                    "holiday_status_id": vacation_leave_type_id,
                    "number_of_days": (
                        vacation_days
                        if vacation_days < company_id.maximum_vacation_days
                        else company_id.maximum_vacation_days
                    ),
                }
            )
            vacation_allocation.action_confirm()
