from odoo import api, fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    foreign_currency_id = fields.Many2one(
        "res.currency", related="company_id.currency_foreign_id", store=True
    )
    foreign_wage = fields.Monetary(currency_field="foreign_currency_id")
    foreign_hourly_wage = fields.Monetary(currency_field="foreign_currency_id")
    contract_foreign_wage = fields.Monetary(
        currency_field="foreign_currency_id", compute="_compute_contract_foreign_wage"
    )
    compute_payroll_using = fields.Selection(related="company_id.compute_payroll_using")
    wage_field_to_use = fields.Selection(
        [
            ("wage", "Wage"),
            ("hourly_wage", "Hourly Wage"),
            ("foreign_wage", "Foreign Wage"),
            ("foreign_hourly_wage", "Foreign Hourly Wage"),
        ],
        help="Field to decide which wage field should be shown on the contract form",
        compute="_compute_wage_field_to_use",
    )

    salary_type = fields.Selection([("fixed", "Fixed"), ("variable", "Variable")], default="fixed")

    structure_type_id = fields.Many2one(required=True)

    @api.depends("wage_type", "compute_payroll_using")
    def _compute_wage_field_to_use(self):
        conditions_for_fields = {
            ("monthly", "base_wage"): "wage",
            ("hourly", "base_wage"): "hourly_wage",
            ("monthly", "foreign_wage"): "foreign_wage",
            ("hourly", "foreign_wage"): "foreign_hourly_wage",
        }
        for contract in self:
            contract.wage_field_to_use = conditions_for_fields[
                (contract.wage_type, contract.compute_payroll_using)
            ]

    @api.depends("foreign_wage", "foreign_hourly_wage")
    def _compute_contract_foreign_wage(self):
        for contract in self:
            contract.contract_foreign_wage = contract._get_contract_foreign_wage()

    def _get_contract_foreign_wage(self):
        if not self:
            return 0
        self.ensure_one()
        return self["foreign_" + self._get_contract_wage_field()]

    def get_vef_wage(self):
        self.ensure_one()
        vef_currency = self.env.ref("base.VEF")
        if self.foreign_currency_id == vef_currency:
            return self._get_contract_foreign_wage()
        return self._get_contract_wage()
        # return self[self.wage_field_to_use]

    def get_integral_daily_wage(self):
        self.ensure_one()
        employee_id = self.employee_id
        employee_salary_payments = employee_id.get_all_payroll_moves()

        if not employee_salary_payments:
            return 0

        last_accrued = employee_salary_payments[-1]["total_accrued"]
        bonus_days_alicuot = employee_id.get_vacation_bonus_days_alicuot()
        profit_sharing_days_alicuot = employee_id.get_profit_sharing_days_alicuot()
        return (last_accrued / 30) + bonus_days_alicuot + profit_sharing_days_alicuot
