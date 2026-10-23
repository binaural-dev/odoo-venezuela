from odoo import models, fields, api, _, Command
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = "account.move"

    guide_number = fields.Char(compute='_compute_guide_number', string="Guide Number", store=True)
    transfer_ids = fields.Many2many("stock.picking", string="Transfers")
    picking_ids = fields.Many2many("stock.picking", column1='account_move_id', column2= 'stock_picking_id', relation='pickings_invoice_rel')
    from_picking = fields.Boolean(string="From Picking", default=False)

    

    @api.depends("picking_ids")
    def _compute_guide_number(self):
        for record in self:
            list_guide_number = [picking.guide_number for picking in record.picking_ids]
            record.guide_number = "/".join(list_guide_number)

    def button_cancel(self):
        """Revert the dispatch-guide invoicing state created by `create_invoice`.

        `stock.picking.create_invoice()` sets `state_guide_dispatch` and bumps
        `sale.order.line.qty_invoiced` by hand when the invoice is created, outside
        Odoo's native invoicing flow. Cancelling the invoice never undoes that on
        its own (nothing is wired to listen for it), which leaves the guide stuck
        as "Invoiced" and the sale order permanently "Fully Invoiced" with no way
        to re-invoice the delivery. Mirror the creation-time side effects here.
        """
        pickings_by_move = {move: move.transfer_ids for move in self if move.transfer_ids}
        res = super().button_cancel()
        for move, pickings in pickings_by_move.items():
            pickings._revert_guide_dispatch_state(move)
            pickings._revert_order_sale_invoiced()
        return res
