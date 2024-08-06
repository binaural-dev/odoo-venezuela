from odoo import models, fields, api

class AccountMoveReportBinauralAccountMove(models.Model):
    _inherit = "account.invoice.report"

    liters_per_unit_total = fields.Float()

    @api.model
    def _select(self):
        res = super()._select()
        res += """,
            line.liters_per_unit_total
        """
        return res