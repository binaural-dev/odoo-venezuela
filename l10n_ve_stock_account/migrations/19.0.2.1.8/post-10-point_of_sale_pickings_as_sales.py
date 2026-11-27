"""Gives the sale transfer reason to the outgoing pickings of the point of sale.

What: recomputes the allowed transfer reasons of the outgoing pickings that come from a point of
sale order or session and still have the self consumption reason. From this version on those
pickings are treated as sales, so the recompute offers sale and export and replaces self
consumption with sale.

Why: a point of sale picking has no sale order, so it fell in "outgoing without sale" and got
self consumption, the first allowed reason. The inventory book then showed point of sale sales in
the self consumption column instead of the outgoing one.

When it does nothing: databases without point_of_sale (no pos_order_id column on stock_picking).

How to revert: set the reason back by hand on the affected pickings; the reason only classifies
the picking (inventory book, dispatch guide), it does not change stock nor accounting.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _column_exists(cr, "stock_picking", "pos_order_id"):
        return

    cr.execute(
        """
        SELECT p.id
          FROM stock_picking p
          JOIN stock_picking_type t ON t.id = p.picking_type_id
          JOIN transfer_reason r ON r.id = p.transfer_reason_id
         WHERE t.code = 'outgoing'
           AND r.code = 'self_consumption'
           AND (p.pos_order_id IS NOT NULL OR p.pos_session_id IS NOT NULL)
        """
    )
    picking_ids = [row[0] for row in cr.fetchall()]
    if not picking_ids:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    pickings = env["stock.picking"].browse(picking_ids)
    pickings._compute_allowed_reason_ids()
    env.flush_all()
    _logger.info(
        "l10n_ve_stock_account: %s point of sale pickings moved from self consumption to sale",
        len(pickings.filtered(lambda p: p.transfer_reason_id.code == "sale")),
    )
