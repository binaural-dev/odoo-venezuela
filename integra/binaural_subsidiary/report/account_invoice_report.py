from odoo import models, fields, api


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    subsidiary = fields.Char()

    @api.model
    def _select(self):
        res = super()._select()
        res += """,
        aac.name AS subsidiary
        """
        return res

    @api.model
    def _from(self):
        res = super()._from()
        res += "LEFT JOIN account_analytic_account aac ON move.account_analytic_id = aac.id"
        return res
