from odoo import models, fields, api

class PurchaseReportBinauralPurchase(models.Model):
    _inherit = 'purchase.report'

    liters_per_unit_total = fields.Float()

    @api.model
    def _select(self):
        return (
            super()._select() + ", l.liters_per_unit_total"
        )

    def _group_by(self):
        return (
            super()._group_by() + ", l.liters_per_unit_total"
        )