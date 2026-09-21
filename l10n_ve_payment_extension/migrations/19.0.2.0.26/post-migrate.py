"""Post-migration for l10n_ve_payment_extension 19.0.2.0.26.

Two changes landed in this module between v17 and v19 for tax.unit
(Unidad Tributaria):

1. tax.unit's own fields (name, value, status) did NOT disappear --
   they moved: v17 declared them directly (`_name = "tax.unit"` in this
   module); v19 moved the `_name` declaration itself to
   l10n_ve_accountant and this module now only `_inherit`s it to add
   `available_date`. Same table, same columns, no data at risk.

2. tax.unit.available_date (Date, required=True) is genuinely NEW. v17
   never recorded a per-record "publish date" for a UT value, so
   existing rows come out of the schema upgrade with
   available_date = NULL. That is NOT harmless here: v19's
   _update_active_status() picks the "currently active" UT by
   `ORDER BY available_date DESC, id DESC LIMIT 1`, and PostgreSQL's
   default NULLS ordering for DESC is NULLS FIRST -- so a record with
   no available_date would sort ahead of every dated one and could get
   incorrectly flagged as the active UT.

This backfills available_date for pre-existing rows using create_date
as the best available stand-in for "when this UT value started being
used" (v17 has no better source), ordered so older UT values keep
earlier dates than newer ones even if they share the same create_date
day. It then re-runs the module's own active-status logic so exactly
one record ends up status=True, consistent with the new ordering rule
-- instead of leaving that to whatever the next unrelated write
happens to trigger.

Float -> Monetary changes on account.retention / account.retention.line
in this same version bump need NO migration: Odoo's Monetary and Float
fields use the identical `double precision` SQL column type, so the
type change is purely an ORM/currency-display concern with nothing to
migrate at the database level.
"""

import logging

_logger = logging.getLogger(__name__)


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _column_exists(cr, "tax_unit", "available_date"):
        _logger.info(
            "l10n_ve_payment_extension post-migrate: tax_unit.available_date "
            "does not exist, skipping backfill"
        )
        return

    cr.execute(
        "SELECT id FROM tax_unit WHERE available_date IS NULL "
        "ORDER BY create_date ASC, id ASC"
    )
    rows = cr.fetchall()
    if not rows:
        _logger.info(
            "l10n_ve_payment_extension post-migrate: no tax.unit row is missing "
            "available_date, nothing to backfill"
        )
    else:
        # Assign create_date (as a plain date) to each row; where several
        # rows share the same create_date day, nudge later ones forward by
        # a day so no two end up tied (tax.unit has a uniqueness constraint
        # on available_date once populated).
        cr.execute(
            """
            WITH ordered AS (
                SELECT id, create_date::date AS base_date,
                       row_number() OVER (
                           PARTITION BY create_date::date ORDER BY id
                       ) - 1 AS offset_days
                FROM tax_unit
                WHERE available_date IS NULL
            )
            UPDATE tax_unit t
            SET available_date = ordered.base_date + ordered.offset_days
            FROM ordered
            WHERE t.id = ordered.id
            """
        )
        _logger.info(
            "l10n_ve_payment_extension post-migrate: backfilled available_date "
            "for %s tax.unit row(s) using create_date as the best available "
            "stand-in (v17 recorded no publish date)",
            len(rows),
        )

    from odoo import api, SUPERUSER_ID

    env = api.Environment(cr, SUPERUSER_ID, {})
    tax_units = env["tax.unit"].search([])
    if tax_units:
        tax_units._update_active_status()
        _logger.info(
            "l10n_ve_payment_extension post-migrate: re-ran _update_active_status() "
            "over %s tax.unit record(s) so exactly one is flagged active under "
            "the new available_date-based ordering",
            len(tax_units),
        )
