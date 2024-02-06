from odoo import api, fields, models


class HrPayslipWorkedDays(models.Model):
    _inherit = "hr.payslip.worked_days"

    foreign_currency_id = fields.Many2one(related="payslip_id.foreign_currency_id")

    foreign_amount = fields.Monetary(
        currency_field="foreign_currency_id",
        compute="_compute_foreign_amount",
        store=True,
        copy=True,
    )

    @api.depends(
        "is_paid",
        "number_of_hours",
        "payslip_id",
        "contract_id.contract_foreign_wage",
        "payslip_id.sum_worked_hours",
    )
    def _compute_foreign_amount(self):
        for worked_days in self:
            if worked_days.payslip_id.edited or worked_days.payslip_id.state not in [
                "draft",
                "verify",
            ]:
                continue
            if not worked_days.contract_id or worked_days.code == "OUT":
                worked_days.amount = 0
                continue
            contract = worked_days.payslip_id.contract_id
            if worked_days.payslip_id.wage_type == "hourly":
                wage = (
                    contract.foreign_hourly_wage
                    if contract.compute_payroll_using == "foreign_wage"
                    else contract.hourly_wage * worked_days.payslip_id.foreign_inverse_rate
                )
                worked_days.foreign_amount = (
                    wage * worked_days.number_of_hours if worked_days.is_paid else 0
                )
            else:
                wage = (
                    contract.contract_foreign_wage
                    if contract.compute_payroll_using == "foreign_wage"
                    else (
                        contract.contract_wage * worked_days.payslip_id.foreign_inverse_rate
                    )
                )
                worked_days.foreign_amount = (
                    wage
                    * worked_days.number_of_hours
                    / (worked_days.payslip_id.sum_worked_hours or 1)
                    if worked_days.is_paid
                    else 0
                )

    @api.depends(
        "is_paid",
        "number_of_hours",
        "payslip_id",
        "contract_id.wage",
        "payslip_id.sum_worked_hours",
    )
    def _compute_amount(self):
        for worked_days in self:
            if worked_days.payslip_id.edited or worked_days.payslip_id.state not in [
                "draft",
                "verify",
            ]:
                continue
            if not worked_days.contract_id or worked_days.code == "OUT":
                worked_days.amount = 0
                continue
            contract = worked_days.payslip_id.contract_id
            if worked_days.payslip_id.wage_type == "hourly":
                wage = (
                    contract.hourly_wage
                    if contract.compute_payroll_using == "base_wage"
                    else contract.foreign_hourly_wage / worked_days.payslip_id.foreign_inverse_rate
                )
                worked_days.amount = (
                    wage * worked_days.number_of_hours if worked_days.is_paid else 0
                )
            else:
                wage = (
                    contract.contract_wage
                    if contract.compute_payroll_using == "base_wage"
                    else (
                        contract.contract_foreign_wage / worked_days.payslip_id.foreign_inverse_rate
                    )
                )
                worked_days.amount = (
                    wage
                    * worked_days.number_of_hours
                    / (worked_days.payslip_id.sum_worked_hours or 1)
                    if worked_days.is_paid
                    else 0
                )
