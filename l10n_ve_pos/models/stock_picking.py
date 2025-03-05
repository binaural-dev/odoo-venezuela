from odoo import models, fields, api, _


class PosOrder(models.Model):
    _inherit = "stock.picking"

    def _create_move_from_pos_order_lines(self, lines):
        res = super()._create_move_from_pos_order_lines(lines)
        self.env.context = self.with_context(
            skip_not_allow_sell_products_validation=True
        ).env.context
        return res
