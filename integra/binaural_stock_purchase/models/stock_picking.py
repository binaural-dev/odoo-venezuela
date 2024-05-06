from odoo import api, fields, models, _

from odoo.exceptions import ValidationError
from odoo.exceptions import UserError

import logging

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    purchase_order_id = fields.Many2one("purchase.order")
    purchase_invoice = fields.Char(related='purchase_order_id.invoice_ids.name')
    purchase_user_id = fields.Many2one(related='purchase_order_id.user_id')

    def set_sale_pos_order(self):
        res = super().set_sale_pos_order()
        for stock in self:
            if not stock.sale_order_id:
                purchase_order = self.env["purchase.order"].search(
                [
                    ("name", "=", stock.origin),
                    ("company_id", "=", self.env.company.id),
                ]
            )
            if purchase_order:
                stock.purchase_order_id = purchase_order
        return res