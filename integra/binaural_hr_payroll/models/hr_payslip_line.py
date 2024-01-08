from odoo import fields, models


class HrPayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    foreign_amount = fields.Monetary()
    foreign_total = fields.Monetary()
