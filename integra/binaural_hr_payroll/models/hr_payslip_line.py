from odoo import api, fields, models


class HrPayslipLine(models.Model):
    _inherit = "hr.payslip.self"

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

    def get_values_for_payroll_move(self):
        self.ensure_one()
        result = {}
        if self.category_id.code == "DED":
            result["total_deduction"] = self.total
            result["foreign_total_deduction"] = self.foreign_total
        if self.category_id.code == "ASIG":
            result["total_assig"] = self.total
            result["foreign_total_assig"] = self.foreign_total
        if self.category_id.code == "BASIC":
            result["total_basic"] = self.total
            result["foreign_total_basic"] = self.foreign_total
        if self.category_id.code == "DEV":
            result["total_accrued"] = self.total
            result["foreign_total_accrued"] = self.foreign_total
        if self.category_id.code == "NET":
            result["total_net"] = self.total
            result["foreign_total_net"] = self.foreign_total

        if self.code == "DDBVM":
            result["vacation_days"] = self.total
        if self.code == "DDVM":
            result["consumed_vacation_days"] = self.total
        if self.code == "PDDVM":
            result["total_vacation"] = self.total
            result["foreign_total_vacation"] = self.foreign_total
        if self.code == "DDBVM":
            result["vacation_bonus_days"] = self.total
        if self.code == "PDDBVM":
            result["total_vacation_bonus"] = self.total
            result["foreign_total_vacation_bonus"] = self.foreign_total
        if self.code == "UTIL":
            result["profit_sharing_payment"] = self.total
            result["foreign_profit_sharing_payment"] = self.foreign_total
        if self.code == "ADPRESTA":
            result["advance_of_benefits"] = self.total
            result["foreign_advance_of_benefits"] = self.foreign_total

        if payroll_structure_category == "liquidation":
            if self.code == "DDVMLIQ":
                vacation_days += self.total
            if self.code == "PDDVMLIQ":
                total_vacation += self.total
                foreign_total_vacation += self.foreign_total
            if self.code == "DDVBMLIQ":
                vacation_bonus_days += self.total
            if self.code == "PDDVBMLIQ":
                total_vacation_bonus += self.total
                foreign_total_vacation_bonus += self.foreign_total
            if self.code == "UTILLIQ":
                profit_sharing_payment += self.total
                foreign_profit_sharing_payment += self.foreign_total
            if self.code == "PRESTA":
                benefits_payment += self.total
                foreign_benefits_payment += self.foreign_total
