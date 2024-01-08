from odoo import fields, models


class HrPayslipWorkedDays(models.Model):
    _inherit = "hr.payslip.worked_days"

    foreign_amount = fields.Monetary()
