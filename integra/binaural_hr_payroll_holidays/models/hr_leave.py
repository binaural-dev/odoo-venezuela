from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _inherit = "hr.leave"

    @api.constrains("date_from", "date_to", "employee_id")
    def _check_date(self):
        for holiday in self:
            if holiday.is_vacation():
                self.env.context = self.with_context(leave_skip_date_check=True).env.context
                continue
        return super()._check_date()

    def is_vacation(self):
        self.ensure_one()
        vacation_leave_type_id = self.env.ref("hr_holidays.holiday_status_cl").id
        return self.holiday_status_id.id == vacation_leave_type_id

    def _get_number_of_days(self, date_from, date_to, employee_id):
        """
        Inherits the original method, so the vacation's leaves don't take into account certain
        work entries to compute the number of days of the leave.
        """
        if not self.is_vacation():
            return super(HrLeave, self)._get_number_of_days(date_from, date_to, employee_id)

        entries_to_skip = (
            self.env.ref("binaural_hr_payroll.hr_work_entry_binaural_holiday").id,
            self.env.ref("binaural_hr_payroll.hr_work_entry_binaural_holiday_not_worked").id,
            self.env.ref("binaural_hr_payroll.hr_work_entry_binaural_weekend").id,
            self.env.ref("binaural_hr_payroll.hr_work_entry_binaural_break_day").id,
        )
        entries = self.env["hr.work.entry"].search(
            [
                ("active", "=", True),
                ("employee_id", "=", employee_id),
                ("date_start", ">=", date_from),
                ("date_stop", "<=", date_to),
                ("work_entry_type_id", "not in", entries_to_skip),
            ]
        )

        employee = self.env["hr.employee"].browse(employee_id)

        # Use sudo otherwise base users can't compute number of days
        contracts = employee.sudo()._get_contracts(date_from, date_to, states=["open", "close"])
        contracts |= employee.sudo()._get_incoming_contracts(date_from, date_to)
        calendar = (
            contracts[:1].resource_calendar_id if contracts else employee.resource_calendar_id
        )  # Note: if len(contracts)>1, the leave creation will crash because of unicity constaint

        hours = sum(entries.sudo()._get_duration_batch().values())
        days = hours / calendar.hours_per_day
        return {"hours": hours, "days": days}
