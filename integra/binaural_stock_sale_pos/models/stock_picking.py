from odoo import api, fields, models, _

from odoo.exceptions import ValidationError
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    pos_order_id = fields.Many2one("pos.order")
    pos_invoice = fields.Char(related='pos_order_id.account_move.name')
    pos_user_id = fields.Many2one(related='pos_order_id.user_id')
    
    def set_sale_pos_order(self):
        res = super().set_sale_pos_order()
        for stock in self:
            pos_order_rec = stock.sale_order_id.pos_order_line_ids.mapped('order_id')
            if pos_order_rec:
                pos_order = self.env["pos.order"].search(
                    [
                        ("name", "=", stock.origin),
                        ("company_id", "=", self.env.company.id),
                    ]
                )
                if pos_order:
                    stock.pos_order_id = pos_order
                    stock.sale_order_id = False
        return res

