from odoo import fields, models


class RetentionLineReport(models.Model):
    _inherit = "retention.line.report"

    account_analytic_id = fields.Many2one("account.analytic.account", string="Subsidiary")

    def _select(self):
        res = super()._select()
        return res + ", rl.account_analytic_id"
