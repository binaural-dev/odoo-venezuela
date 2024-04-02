import locale
from odoo import api, fields, models
from babel.dates import format_date


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    date = fields.Date(compute="_compute_date", store=True, readonly=False)

    @api.depends("date_to")
    def _compute_date(self):
        for slip in self:
            slip.date = slip.date_to

    def _action_create_account_move(self):
        res = super()._action_create_account_move()

        locale = self._context.get("lang") or "es_VE"

        for slip in self:
            month = format_date(slip.date, "MMMM Y", locale=locale).capitalize()
            employee = slip.employee_id

            slip.move_id.write(
                {
                    "foreign_rate": slip.foreign_rate,
                    "foreign_inverse_rate": slip.foreign_inverse_rate,
                    "ref": f"{month} - {slip.number} - {employee.prefix_vat}{employee.vat}",
                }
            )
        return res

    def _prepare_line_values(self, line, account_id, date, debit, credit):
        values = super()._prepare_line_values(line, account_id, date, debit, credit)

        foreign_amount = abs(line.foreign_total)
        foreign_debit = foreign_amount if values["debit"] > 0.0 else 0.0
        foreign_credit = foreign_amount if values["credit"] > 0.0 else 0.0

        return {
            **values,
            "foreign_debit": foreign_debit,
            "foreign_credit": foreign_credit,
            "not_foreign_recalculate": True,
        }
