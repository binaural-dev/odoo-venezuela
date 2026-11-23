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

    def _get_picking_revert_data(self):
        """Capture linked pickings and invoiced quantities per product before
        the move is cancelled or unlinked (only for moves not yet cancelled)."""
        revert_data = []
        for move in self:
            if move.transfer_ids and move.state != "cancel":
                qty_by_product = {}
                for line in move.invoice_line_ids:
                    if line.product_id:
                        qty_by_product[line.product_id.id] = (
                            qty_by_product.get(line.product_id.id, 0.0) + line.quantity
                        )
                revert_data.append((move.id, move.transfer_ids, qty_by_product))
        return revert_data

    def _apply_picking_revert(self, revert_data):
        """Revert dispatch-guide state and sale order invoiced quantities for
        moves that were just cancelled or deleted."""
        for move_id, pickings, qty_by_product in revert_data:
            pickings._revert_guide_dispatch_state(move_id)
            pickings._revert_order_sale_invoiced(
                cancelled_invoice=move_id,
                cancelled_qty_by_product=qty_by_product,
            )

    def button_cancel(self):
        """Revert the dispatch-guide invoicing state created by `create_invoice`.

        `stock.picking.create_invoice()` sets `state_guide_dispatch` and bumps
        `sale.order.line.qty_invoiced` by hand when the invoice is created, outside
        Odoo's native invoicing flow. Cancelling the invoice never undoes that on
        its own (nothing is wired to listen for it), which leaves the guide stuck
        as "Invoiced" and the sale order permanently "Fully Invoiced" with no way
        to re-invoice the delivery. Mirror the creation-time side effects here.
        """
        revert_data = self._get_picking_revert_data()
        res = super().button_cancel()
        self._apply_picking_revert(revert_data)
        return res

    def button_draft(self):
        """Re-apply dispatch-guide and sale-order invoicing state when a
        cancelled picking-linked invoice is reset to draft.

        Cancelling a picking-linked invoice reverts `state_guide_dispatch` and
        `qty_invoiced`. If that cancelled invoice is later reset to draft so it
        can be posted again, it becomes an active invoice on the picking once
        more and must restore the invoiced state to prevent duplicate billing.
        """
        pickings_per_move = [
            move.transfer_ids
            for move in self
            if move.transfer_ids and move.state == "cancel"
        ]
        res = super().button_draft()
        for pickings in pickings_per_move:
            pickings._reapply_guide_invoicing_state()
        return res

    def unlink(self):
        """Revert dispatch-guide invoicing state when a linked invoice is deleted.

        Draft invoices created from a picking can be deleted directly without
        calling `button_cancel()`; capture linked pickings before `super().unlink()`
        removes the records and revert their state right after deletion succeeds.
        """
        revert_data = self._get_picking_revert_data()
        res = super().unlink()
        self._apply_picking_revert(revert_data)
        return res

    def _get_tax_grouped_lines(self):
        """
        Agrupa las líneas de factura por el conjunto de impuestos que tienen aplicados.
        Retorna un diccionario: { tuple(ids_impuestos): {'base_amount': suma_base, 'taxes': recordset_impuestos} }
        """
        self.ensure_one()
        tax_groups = {}
        for line in self.invoice_line_ids:
            tax_ids = line.tax_ids.ids
            tax_key = tuple(sorted(tax_ids))

            if tax_key not in tax_groups:
                tax_groups[tax_key] = {
                    'base_amount': 0.0,
                    'taxes': line.tax_ids,
                }
            tax_groups[tax_key]['base_amount'] += line.price_subtotal
        return tax_groups
