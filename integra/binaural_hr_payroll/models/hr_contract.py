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

    @api.depends("foreign_wage", "foreign_hourly_wage")
    def _compute_contract_foreign_wage(self):
        for contract in self:
            contract.contract_foreign_wage = contract._get_contract_foreign_wage()

    def _get_contract_foreign_wage(self):
        if not self:
            return 0
        self.ensure_one()
        return self["foreign_" + self._get_contract_wage_field()]
