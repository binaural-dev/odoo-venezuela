from odoo import models, fields

class SaleReportBinauralSale(models.Model):
    _inherit = 'sale.report'

    liters_per_unit_total = fields.Float()

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res['liters_per_unit_total'] = "l.liters_per_unit_total"
        return res

    def _group_by_sale(self):
        res = super()._group_by_sale()
        res += """,
            l.liters_per_unit_total
            """
        return res