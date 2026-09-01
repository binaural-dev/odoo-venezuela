"""Pre-migration for l10n_ve_rate: v17 -> v19 field rename.

v17 declared res.company.currency_foreign_id (Many2one res.currency).
v19 renamed it, with identical semantics and type, to
res.company.foreign_currency_id. Every downstream module that reads this
field via `env.company.currency_foreign_id` / `related=...` (confirmed in
l10n_ve_accountant, binaural_account_asset, binaural_account_reports,
binaural_analytic, binaural_payment, binaural_list_price_foreign,
binaural_purchase, and likely more) depends on this rename landing before
their own schema is touched.

Runs BEFORE the new v19 schema is applied, while the old column name is
still what's on disk: renames the raw DB column in place so no data is
lost and no separate backfill/drop step is needed afterward -- the ORM
will find the column already named foreign_currency_id when it builds
the v19 field.

res.config.settings is a TransientModel (not persisted across sessions),
so it needs no migration of its own; it is only re-declared here as a
related field to res.company.
"""

import logging

_logger = logging.getLogger(__name__)

RENAME = ("res_company", "currency_foreign_id", "foreign_currency_id")


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    table, old_column, new_column = RENAME
    _logger.info("l10n_ve_rate pre-migrate: renaming %s.%s -> %s", table, old_column, new_column)

    if not _column_exists(cr, table, old_column):
        _logger.info(
            "  %s.%s does not exist (already migrated or fresh install), skipping",
            table, old_column,
        )
        return

    if _column_exists(cr, table, new_column):
        _logger.warning(
            "  Both %s.%s and %s.%s exist -- likely a re-run after a partial "
            "migration. Leaving both columns untouched; resolve manually.",
            table, old_column, table, new_column,
        )
        return

    cr.execute(
        f'ALTER TABLE "{table}" RENAME COLUMN "{old_column}" TO "{new_column}"'  # noqa: S608
    )
    _logger.info("  Renamed %s.%s -> %s.%s", table, old_column, table, new_column)
