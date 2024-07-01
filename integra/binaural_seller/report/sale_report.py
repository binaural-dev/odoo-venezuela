from odoo import models, fields


class SaleReportBinauralSale(models.Model):
    _inherit = "sale.report"

    seller_id = fields.Many2one(
        "hr.employee", string="Vendedores", help="Vendedor encargado de la venta"
    )

    def _select_additional_fields(self):
        res = super()._select_additional_fields()
        res["seller_id"] = "s.seller_id"
        return res

    def _group_by_sale(self):
        res = super()._group_by_sale()
        res += """,
            s.seller_id
            """
        return res
