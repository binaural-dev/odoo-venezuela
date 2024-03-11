from functools import partial

from odoo import models, fields


class PosOrderReport(models.Model):
    _inherit = "report.pos.order"

    brand_id = fields.Many2one("product.brand", string="Brand")

    def _select(self):
        return super()._select() + ",pt.brand_id As brand_id"

    def _group_by(self):
        res = super()._group_by()
        res += """,
            pt.brand_id
            """
        return res

    def _from(self):
        res = super()._from()
        res += """ LEFT JOIN product_brand br ON pt.brand_id = br.id """
        return res
