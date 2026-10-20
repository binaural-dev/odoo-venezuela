from odoo import models, fields, api, _


class PosOrder(models.Model):
    _inherit = "stock.picking"

    def _create_move_from_pos_order_lines(self, lines):
        return super(
            PosOrder,
            self.with_context(skip_not_allow_sell_products_validation=True),
        )._create_move_from_pos_order_lines(lines)
