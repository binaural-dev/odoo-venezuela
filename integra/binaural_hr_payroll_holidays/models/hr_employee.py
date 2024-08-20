from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class HrEmpoyee(models.Model):
    _inherit = "hr.employee"

    last_vacation_allocation_date = fields.Date()

    @api.model
    def get_employees_having_entry_date_month_and_day(self, date_to_check=fields.Date.today()):
        """
        Check if the employee has one year or more of seniority and the entry day and month are the
        same as the ones on the date passed as parameter.

        Parameters
        ----------
        date_to_check : date
            The date to check.

        Returns
        -------
        hr.employee recordset
            The employees which entry day and month are the same as the ones on the date passed as
            parameter.
        """

        employees = self.search(
            [("active", "=", True), ("last_vacation_allocation_date", "!=", date_to_check)]
        )
        month = date_to_check.month
        day = date_to_check.day
        return employees.filtered(
            lambda e: e._get_seniority_in_years() >= 1
            and e.entry_date.month == month
            and e.entry_date.day == day
        )

    def get_not_taken_vacation_days(self):
        self.ensure_one()
        days = 0
        leave_type_vacation_id = self.env["ir.model.data"]._xmlid_to_res_id(
            "hr_holidays.holiday_status_cl", raise_if_not_found=False
        )
        vacation_allocations = self.env["hr.leave.allocation"].search(
            [
                ("employee_id", "=", self.id),
                ("holiday_status_id", "=", leave_type_vacation_id),
            ]
        )
        for allocation in vacation_allocations:
            days += allocation.max_leaves - allocation.leaves_taken
        return days
