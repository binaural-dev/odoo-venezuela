from odoo import api, fields, models
from collections import defaultdict


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

    def _cancel_work_entry_conflict(self):
        """
        This overrides the standard behaviour for vacation leaves.

        When the leaves are vacations the entries of the selected period for the employee are
        overriten to comply with the entries that are on the leave type. This means that the type of
        the entries for holidays and break days are replaced with the corresponding holidays and
        break days entry types  that are selected on the holiday_work_entry_type_id and the
        break_day_work_entry_type_id fields of the leave type.

        The type of the other entries on the period is replaced with the one on the field
        work_entry_type_id of the leave type.
        """
        not_vacation_leaves = self.filtered(lambda l: not l.is_vacation())
        entries_to_skip = (
            self.env.ref("binaural_hr_payroll.hr_work_entry_binaural_holiday").id,
            self.env.ref("binaural_hr_payroll.hr_work_entry_binaural_holiday_not_worked").id,
            self.env.ref("binaural_hr_payroll.hr_work_entry_binaural_weekend").id,
            self.env.ref("binaural_hr_payroll.hr_work_entry_binaural_break_day").id,
        )
        for leave in self - not_vacation_leaves:
            entries_replacing = {
                entries_to_skip[0]: leave.holiday_status_id.holiday_work_entry_type_id.id,
                entries_to_skip[1]: leave.holiday_status_id.holiday_work_entry_type_id.id,
                entries_to_skip[2]: leave.holiday_status_id.break_day_work_entry_type_id.id,
                entries_to_skip[3]: leave.holiday_status_id.break_day_work_entry_type_id.id,
            }
            employee_work_entries = self.env["hr.work.entry"].search(
                [
                    ("active", "=", True),
                    ("date_start", ">=", leave.date_from),
                    ("date_stop", "<=", leave.date_to),
                    ("employee_id", "=", leave.employee_id.id),
                ]
            )
            for entry in employee_work_entries.sudo():
                if entry.work_entry_type_id.id not in entries_replacing:
                    entry.work_entry_type_id = leave.holiday_status_id.work_entry_type_id.id
                else:
                    entry.work_entry_type_id = entries_replacing[entry.work_entry_type_id.id]

                entry.leave_id = leave.id

        super(HrLeave, not_vacation_leaves)._cancel_work_entry_conflict()
