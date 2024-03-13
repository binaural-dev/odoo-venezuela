from odoo import api, fields, models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _prepare_line_values(self, line, account_id, date, debit, credit):
        values = super()._prepare_line_values(line, account_id, date, debit, credit)

        foreign_amount = line.foreign_total
        foreign_debit = foreign_amount if values["debit"] > 0.0 else 0.0
        foreign_credit = foreign_amount if values["credit"] > 0.0 else 0.0

        return {
            **values,
            "foreign_debit": foreign_debit,
            "foreign_credit": foreign_credit,
            "not_foreign_recalculate": True,
        }
