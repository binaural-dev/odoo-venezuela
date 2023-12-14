from odoo import fields, models


class PurchaseReport(models.Model):
    _inherit = "purchase.report"

    subsidiary = fields.Char()

    def _select(self):
        res = super()._select()
        res += """,
        aac.name AS subsidiary
        """
        return res

    def _from(self):
        res = super()._from()
        res += "LEFT JOIN account_analytic_account aac ON po.account_analytic_id = aac.id"
        return res

    def _group_by(self):
        res = super()._group_by()
        res += """,
        aac.name
        """
        return res
