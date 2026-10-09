"""Fill invoice_date_display_datetime on the invoices coming from v17.

What: creates the account_move.invoice_date_display_datetime column and sets it to the
    invoice_date_display date at 12:00 (UTC). Where invoice_date_display is empty it stays empty.

Why: the field does not exist in v17. This module's post_init_hook fills it, but that hook only runs
    on install: a homologated client, which already has the module, gets it empty on every invoice.
    In v19 the field is written together with invoice_date_display (account.move create/write), so
    migrated invoices ended up different from new ones.

    The time of the v17 invoices is not stored anywhere. Noon UTC is used so that, in any client
    time zone, the field shows the same day as invoice_date_display. The install hook uses the time
    of the install, which in Venezuela (UTC-4) changes the day of anything registered after 20:00.

    It runs after the l10n_ve_accountant pre- script (19.0.1.1.2), which already set
    invoice_date_display to the v17 date: this module depends on that one.

If it does not run: migrated invoices are left without this field, and whatever sorts by it sends
    them to the start or the end of the list.

How to revert: not needed. The field did not exist in v17, so no data is overwritten.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return
    if not util.column_exists(cr, "account_move", "invoice_date_display"):
        return

    util.create_column(cr, "account_move", "invoice_date_display_datetime", "timestamp")
    count = util.explode_execute(
        cr,
        """
        UPDATE account_move
           SET invoice_date_display_datetime = invoice_date_display + time '12:00'
         WHERE invoice_date_display IS NOT NULL
           AND invoice_date_display_datetime IS NULL
        """,
        table="account_move",
    )
    _logger.info("invoice_date_display_datetime filled on %s moves", count)
