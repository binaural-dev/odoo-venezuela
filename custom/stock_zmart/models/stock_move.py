import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero, float_round

_logger = logging.getLogger(__name__)

class StockMove(models.Model):
    _inherit = "stock.move"

    def _quantity_done_set(self):
        def _process_decrease(move, quantity):
            """Prioritize decrease the ml without reserved qty"""
            res_mls = move._get_move_lines().sorted(lambda ml: float_is_zero(ml.reserved_uom_qty, precision_rounding=ml.product_uom_id.rounding), reverse=True)
            qty_to_unreserve = move.reserved_availability - move.product_uom_qty
            for ml in res_mls:
                if float_is_zero(quantity, precision_rounding=move.product_uom.rounding):
                    break
                qty_ml_dec = min(ml.qty_done, ml.product_uom_id._compute_quantity(quantity, ml.product_uom_id, round=False))
                if float_is_zero(qty_ml_dec, precision_rounding=ml.product_uom_id.rounding):
                    continue
                ml.qty_done -= qty_ml_dec
                quantity -= move.product_uom._compute_quantity(qty_ml_dec, move.product_uom, round=False)
                # Unreserve
                if (not move.picking_id.immediate_transfer and move.reserved_availability < move.product_uom_qty):
                    continue
                if float_compare(ml.reserved_uom_qty, ml.qty_done, precision_rounding=ml.product_uom_id.rounding) <= 0:
                    continue
                if move.picking_id.immediate_transfer:
                    ml.reserved_uom_qty = ml.qty_done
                elif float_compare(qty_to_unreserve, 0, precision_rounding=move.product_uom.rounding) > 0:
                    qty_unreserved = min(qty_to_unreserve, ml.reserved_qty - ml.qty_done)
                    ml.reserved_uom_qty = ml.reserved_qty - qty_unreserved
                    qty_to_unreserve -= qty_unreserved

        def _process_increase(move, quantity):
            moves = move
            if move.picking_id.immediate_transfer:
                moves = move._action_confirm(merge=False)
            # Kits, already handle in action_explode, should be clean in master
            if len(moves) > 1:
                return
            if move.reserved_availability < move.quantity_done and move.state not in ['done', 'cancel']:
                move._action_assign(force_qty=move.quantity_done)
            move._set_quantity_done(quantity)

        err = []
        for move in self:

            if move.quantity_done < 0 or move.quantity_done > move.reserved_availability:
                raise UserError(_("You cannot validate quantities greater than those reserved or lower than cero"))

            uom_qty = float_round(move.quantity_done, precision_rounding=move.product_uom.rounding, rounding_method='HALF-UP')
            precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            qty = float_round(move.quantity_done, precision_digits=precision_digits, rounding_method='HALF-UP')
            if float_compare(uom_qty, qty, precision_digits=precision_digits) != 0:
                err.append(_("""
The quantity done for the product %s doesn't respect the rounding precision defined on the unit of measure %s.
Please change the quantity done or the rounding precision of your unit of measure.""",
                             move.product_id.display_name, move.product_uom.display_name))
                continue
            delta_qty = move.quantity_done - move._quantity_done_sml()
            if float_compare(delta_qty, 0, precision_rounding=move.product_uom.rounding) > 0:
                _process_increase(move, delta_qty)
            elif float_compare(delta_qty, 0, precision_rounding=move.product_uom.rounding) < 0:
                _process_decrease(move, abs(delta_qty))
        if err:
            raise UserError('\n'.join(err))

