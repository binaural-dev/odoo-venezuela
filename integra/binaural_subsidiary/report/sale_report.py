from odoo import models, fields


class SaleReportBinauralSale(models.Model):
    _inherit = "sale.report"

    subsidiary_id = fields.Many2one("account.analytic.account")

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res["subsidiary_id"] = "s.subsidiary_id"
        return res

    def _group_by_sale(self):
        res = super()._group_by_sale()
        res += """,
            s.subsidiary_id
        """
        return res
