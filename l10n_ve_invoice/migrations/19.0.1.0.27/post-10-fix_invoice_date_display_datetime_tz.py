"""Fix the day of invoice_date_display_datetime on the existing moves.

What: for each company, takes the moves whose invoice_date_display_datetime, read in the company
    time zone (partner tz, America/Caracas if empty), falls on a day other than invoice_date_display,
    keeps that local time and puts the invoice_date_display day on it.

Why: account.move create/write built the field as fields.Datetime.now() (UTC) with the day replaced
    by invoice_date_display (a local date). From 20:00 in Venezuela (UTC-4) the UTC time is already
    the next day, so the field showed the previous day. The code now takes day and time from the
    same time zone (the user's, as context_today does); this script fixes what was already stored.
    The user who registered each move is not known here, so the company time zone is used, which is
    the one l10n_ve_base gives the users by default. The time shown to the user was right, only the
    day was off, so the local time is kept.

If it does not run: the documents registered after 20:00 keep showing the previous day, and the
    sales book and the TFHKA digital invoice (which take their date/time from this field) keep it.

How to revert: not reversible from the data: once fixed, those moves cannot be told apart from the
    rest. Only the moves whose local day did not match invoice_date_display are touched.

Ticket: HD #15954
"""

import logging

from odoo.addons.l10n_ve_base.models.res_partner import DEFAULT_TZ

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT DISTINCT am.company_id, COALESCE(p.tz, %s)
          FROM account_move am
          JOIN res_company c ON c.id = am.company_id
          JOIN res_partner p ON p.id = c.partner_id
         WHERE am.invoice_date_display_datetime IS NOT NULL
        """,
        [DEFAULT_TZ],
    )
    for company_id, tz in cr.fetchall():
        cr.execute(
            """
            UPDATE account_move
               SET invoice_date_display_datetime =
                   ((invoice_date_display
                     + ((invoice_date_display_datetime AT TIME ZONE 'UTC')
                        AT TIME ZONE %(tz)s)::time)
                    AT TIME ZONE %(tz)s) AT TIME ZONE 'UTC'
             WHERE company_id = %(company_id)s
               AND invoice_date_display IS NOT NULL
               AND invoice_date_display_datetime IS NOT NULL
               AND ((invoice_date_display_datetime AT TIME ZONE 'UTC')
                    AT TIME ZONE %(tz)s)::date <> invoice_date_display
            """,
            {"tz": tz, "company_id": company_id},
        )
        _logger.info(
            "invoice_date_display_datetime fixed on %s moves (company %s, %s)",
            cr.rowcount,
            company_id,
            tz,
        )
