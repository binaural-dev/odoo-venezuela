"""Recalculate the residual and the payment state of the draft invoices left as "Paid".

What: for every draft invoice/receipt with a total different from 0 and a residual of 0 it
    recomputes amount_residual, amount_residual_signed and payment_state. Drafts that already
    have a residual and any posted invoice are not touched, so running it twice changes nothing.

Why: until this version the summaries of tax_totals read amounts of the invoice while the
    residual of a draft (which core derives from tax_totals) was being computed, so the residual
    was stored as 0 and the draft showed as "Paid" (ticket 86558). The code is fixed here; the
    drafts already saved keep the 0 until they are recomputed.

If it does not run: those drafts keep showing "Paid" with a residual of 0 until someone edits them.

How to revert: it is not reverted. It replaces the wrong residual (0) with the one derived from
    the invoice; the previous value is the bug itself.

Task: https://binaural.odoo.com/odoo/action-341/86558
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

FIELDS = ("amount_residual", "amount_residual_signed", "payment_state")


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute(
        """
        SELECT id FROM account_move
         WHERE state = 'draft'
           AND move_type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund',
                             'out_receipt', 'in_receipt')
           AND COALESCE(amount_total, 0) != 0
           AND COALESCE(amount_residual, 0) = 0
        """
    )
    ids = [row[0] for row in cr.fetchall()]
    if not ids:
        return
    moves = env["account.move"].browse(ids)
    for field_name in FIELDS:
        env.add_to_compute(moves._fields[field_name], moves)
    env.flush_all()
    _logger.info("Recomputed the residual of %s draft invoices left as paid.", len(ids))
