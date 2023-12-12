from odoo import models, fields


class SaleReportBinauralSale(models.Model):
    _inherit = "sale.report"

    subsidiary = fields.Char()

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res["subsidiary"] = "aac.name"
        return res

    def _from_sale(self):
        res = super()._from_sale()
        res += """ LEFT JOIN account_analytic_account aac ON s.analytic_account_id = aac.id """
        return res

    def _group_by_sale(self):
        res = super()._group_by_sale()
        res += """,
            aac.name
        """
        return res
