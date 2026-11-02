"""Create invoice_date_display with the v17 invoice date, before the ORM fills it with today.

What: creates the account_move.invoice_date_display column and fills it with invoice_date. Where
    invoice_date is empty (journal entries, undated drafts) it stays empty too.

Why: the field does not exist in v17. In v19 this module declares it with
    default=fields.Date.context_today, and when the ORM creates the column it writes that default on
    every row: the day of the -u all. That is how all 151,110 account_move rows of
    19_proalca_run15 ended up (2026-09-22). It is not only what is displayed:
    _get_accounting_date_source returns invoice_date_display before date, so any recompute of date
    on a migrated invoice would move it to the migration day.

    In v17 the invoice date was invoice_date. In v19 that field becomes the "rate date" and
    invoice_date_display becomes the fiscal date, so the value each migrated invoice must get is its
    invoice_date.

    It runs in pre- because the ORM does not apply the default if the column already exists when the
    model is loaded.

If it does not run: every migrated invoice shows the migration day as its invoice date, and the
    reports that sort or filter by it (purchase and sales books) come out wrong.

How to revert: not needed. The field did not exist in v17, so no data is overwritten, and
    invoice_date stays untouched.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return

    util.create_column(cr, "account_move", "invoice_date_display", "date")
    count = util.explode_execute(
        cr,
        """
        UPDATE account_move
           SET invoice_date_display = invoice_date
         WHERE invoice_date_display IS DISTINCT FROM invoice_date
        """,
        table="account_move",
    )
    _logger.info("invoice_date_display taken from invoice_date on %s moves", count)
