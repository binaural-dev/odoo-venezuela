from odoo import api, fields, models


class HrContract(models.Model):
    _inherit = "hr.contract"

    analytic_account_id = fields.Many2one(compute="_compute_analytic_account_id", store=True)

    @api.depends("department_id")
    def _compute_analytic_account_id(self):
        for contract in self:
            if not contract.analytic_account_id:
                contract.analytic_account_id = contract.department_id.analytic_account_id
