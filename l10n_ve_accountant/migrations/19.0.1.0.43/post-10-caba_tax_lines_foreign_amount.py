"""Recalculate the alternate amount of the tax lines of the cash basis entries that have it at 0.

What: for every cash basis entry (account.move with tax_cash_basis_origin_move_id) it recomputes
    foreign_debit / foreign_credit / foreign_balance of the lines that have the alternate amount
    at 0 although their balance is not. Entries and lines that already have it are not touched,
    so running it twice changes nothing.

Why: until this version account.move.line._get_foreign_value returned foreign_balance for the
    'tax' lines of those entries. The core copies display_type = 'tax' to them but creates them
    with foreign_balance = 0, so the IVA lines (transition account and final account) were left
    with the alternate amount at 0 while the base lines had it (ticket #16240; same bug fixed in
    v17 with ticket #10703). The code is fixed here; the entries already generated keep the 0.

If it does not run: the old cash basis entries keep the alternate amount of their tax lines at 0
    (the alternate-currency tax book and reports under-report them). New entries are fine.

How to revert: not needed, the values are derived from the move (amount_currency or its rate);
    there is no data to restore.

Task: https://www.binauraldev.com/odoo/my-tickets/16240
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def recompute_caba_foreign_amounts(env):
    """Recompute the alternate amount of the cash basis lines left at 0. Returns the lines."""
    Line = env["account.move.line"].with_context(active_test=False)
    lines = Line.search(
        [
            ("move_id.tax_cash_basis_origin_move_id", "!=", False),
            ("display_type", "in", ("tax", "payment_term")),
            ("foreign_debit", "=", 0),
            ("foreign_credit", "=", 0),
            "|",
            ("debit", "!=", 0),
            ("credit", "!=", 0),
        ]
    )
    if lines:
        env.add_to_compute(Line._fields["foreign_debit"], lines)
        env.add_to_compute(Line._fields["foreign_credit"], lines)
        lines.flush_recordset()
    return lines


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = recompute_caba_foreign_amounts(env)
    _logger.info(
        "%s cash basis lines in %s entries recomputed",
        len(lines),
        len(lines.move_id),
    )
