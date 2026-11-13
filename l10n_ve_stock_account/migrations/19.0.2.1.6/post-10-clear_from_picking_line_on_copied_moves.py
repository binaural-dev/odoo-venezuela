"""Clears from_picking_line on the lines of credit and debit notes copied from an invoice.

What: sets from_picking_line = False on the lines of every move that was
created as a copy of another one: credit notes made with "Credit Note" /
reverse (reversed_entry_id) and, when account_debit_note is installed, debit
notes that copied the lines of the original invoice (debit_origin_id). Every
state is covered, so a posted note that is later reset to draft can be edited
too.

Why: the field had no copy=False, so reversing an invoice created from a
picking copied the flag to the note, and the invoice form made the quantity,
price, product, account, label and discount of those lines read-only. A
partial credit note was impossible (ticket 16194). From
this version on the field is copy=False; this script fixes the notes created
before.

What it does not touch: credit notes created from a picking return
(create_customer_credit / create_vendor_credit). They set the flag on purpose
and have no reversed_entry_id nor debit_origin_id.

How to revert: not needed. The flag only drives the read-only state of the
invoice lines in the form view; no business logic reads it.

Ticket: https://www.binauraldev.com/odoo/my-tickets/16194
"""

import logging

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    origin_conditions = ["m.reversed_entry_id IS NOT NULL"]
    if _column_exists(cr, "account_move", "debit_origin_id"):
        origin_conditions.append("m.debit_origin_id IS NOT NULL")

    cr.execute(
        f"""
        UPDATE account_move_line l
           SET from_picking_line = FALSE
          FROM account_move m
         WHERE m.id = l.move_id
           AND l.from_picking_line
           AND ({" OR ".join(origin_conditions)})
        RETURNING l.move_id
        """
    )
    move_ids = sorted({row[0] for row in cr.fetchall()})
    _logger.info(
        "Cleared from_picking_line on the lines of %s copied note(s): %s",
        len(move_ids),
        move_ids,
    )
