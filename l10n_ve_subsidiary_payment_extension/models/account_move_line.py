from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # override 
    @api.depends("product_id.ciu_ids")
    def _compute_ciu_id(self):
        for line in self:
            if not line.product_id or line.ciu_id or not line.product_id.ciu_ids:
                continue
            if not line.move_id.account_analytic_id.municipality_id:
                line.ciu_id = line.product_id.ciu_ids[0]
                continue
            line.ciu_id = line.product_id.ciu_ids.filtered(
                lambda c: c.municipality_id == line.move_id.account_analytic_id.municipality_id
            )
