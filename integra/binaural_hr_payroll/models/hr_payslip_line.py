from odoo import api, fields, models


class HrPayslipLine(models.Model):
    _inherit = "hr.payslip.line"

    foreign_currency_id = fields.Many2one(related="slip_id.foreign_currency_id")

    foreign_amount = fields.Monetary(currency_field="foreign_currency_id")
    foreign_total = fields.Monetary(
        compute="_compute_foreign_total", store=True, currency_field="foreign_currency_id"
    )

    employee_name = fields.Char(related="employee_id.name")
    employee_vat = fields.Char(related="employee_id.vat")
    employee_job_id = fields.Many2one("hr.job", related="employee_id.job_id")
    employee_department_id = fields.Many2one(
        "hr.department", string="Departament", related="employee_id.department_id"
    )
    category_code = fields.Char(related="category_id.code")
    slip_state = fields.Selection(related="slip_id.state")

    @api.depends("quantity", "amount", "rate")
    def _compute_foreign_total(self):
        for line in self:
            line.foreign_total = float(line.quantity) * line.foreign_amount * line.rate / 100
