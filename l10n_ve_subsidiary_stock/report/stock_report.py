from odoo import fields, models


class StockReport(models.Model):
    _inherit = "stock.report"

    subsidiary_id = fields.Many2one("account.analytic.account", string="Subsidiary")

    def _select(self):
        select_str = super()._select()
        return (
            select_str
            + ", COALESCE(sm.subsidiary_origin_id, sm.subsidiary_dest_id) AS subsidiary_id "
        )

    def _group_by(self):
        group_by_str = super()._group_by()
        return group_by_str + ", subsidiary_id "
