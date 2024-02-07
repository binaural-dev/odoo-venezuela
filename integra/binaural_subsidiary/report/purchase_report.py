from odoo import fields, models


class PurchaseReport(models.Model):
    _inherit = "purchase.report"

    subsidiary_id = fields.Many2one("account.analytic.account")

    def _select(self):
        res = super()._select()
        res += """,
            po.account_analytic_id AS subsidiary_id
        """
        return res

    def _group_by(self):
        res = super()._group_by()
        res += """,
            po.account_analytic_id
        """
        return res
