from odoo import fields, models


class PosOrderReport(models.Model):
    _inherit = "report.pos.order"

    subsidiary_id = fields.Many2one("account.analytic.account", string="Subsidiary")

    def _select(self):
        select = super()._select()
        return (
            select
            + """
        , s.sh_pos_order_analytic_account AS subsidiary_id
        """
        )

    def _group_by(self):
        group_by = super()._group_by()

        return (
            group_by
            + """
        , s.sh_pos_order_analytic_account
        """
        )
