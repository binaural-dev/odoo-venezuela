from odoo import models, fields, api


class AccountInvoiceReport(models.Model):
    _inherit = "account.invoice.report"

    subsidiary_id = fields.Many2one("account.analytic.account")

    @api.model
    def _select(self):
        res = super()._select()
        res += """,
            move.account_analytic_id AS subsidiary_id
        """
        return res
