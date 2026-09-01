"""Pre-migration for l10n_ve_accountant 19.0.1.0.14: absorbs l10n_ve_tax
(v17), which has NO module of its own in v19 -- its IVA aliquot
configuration was folded directly into l10n_ve_accountant.

Verified field-by-field (grep against both modules' actual models/):

SAME COLUMN in v19's l10n_ve_accountant (res.company /
res.config.settings unless noted) -- data is already in place, no
action needed: unique_tax, show_discount_on_moves, exent_aliquot_sale,
general_aliquot_sale, reduced_aliquot_sale, extend_aliquot_sale,
not_show_reduced_aliquot_sale, not_show_extend_aliquot_sale,
exent_aliquot_purchase, general_aliquot_purchase,
reduced_aliquot_purchase, extend_aliquot_purchase,
not_show_reduced_aliquot_purchase, not_show_extend_aliquot_purchase,
config_deductible_tax, no_deductible_general_aliquot_purchase,
no_deductible_reduced_aliquot_purchase,
no_deductible_extend_aliquot_purchase,
exent_aliquot_purchase_international,
general_aliquot_purchase_international,
reduced_aliquot_purchase_international,
extend_aliquot_purchase_international,
not_show_general_aliquot_purchase_international,
not_show_reduced_aliquot_purchase_international,
not_show_extend_aliquot_purchase_international,
not_show_total_purchases_with_international_iva,
not_show_exempt_total_purchases, not_show_total_purchases_international;
plus account_move_line.config_deductible_tax/not_deductible_tax and
account_journal.is_purchase_international.

RENAMED (real data migration, done below):
  account_move_line.international_purchase_exempt_product (v17)
  -> account_move_line.international_purchase_exent_product (v19)
  Same boolean, just a typo fix in the column name ("exempt" -> "exent").

NO v19 FIELD AT ALL -- backed up here, then dropped in post-migrate.py,
NOT migrated (nothing in l10n_ve_accountant or anywhere else in v19
receives them):
  res_company / res_config_settings:
    not_show_total_purchases_with_iva
    not_show_national_exempt_total_purchases
    not_show_total_purchases_national
    zero_aliquot_sale_international
  account_journal:
    is_sale_international
"""

import logging

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "l10n_ve_accountant_migration_v17_backup"

DROPPED_COLUMNS = {
    "res_company": [
        "not_show_total_purchases_with_iva",
        "not_show_national_exempt_total_purchases",
        "not_show_total_purchases_national",
        "zero_aliquot_sale_international",
    ],
    "account_journal": ["is_sale_international"],
}

RENAMED_COLUMNS = [
    ("account_move_line", "international_purchase_exempt_product", "international_purchase_exent_product"),
]


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def _ensure_backup_table(cr):
    cr.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {BACKUP_TABLE} (
            id SERIAL PRIMARY KEY,
            source_table VARCHAR NOT NULL,
            source_column VARCHAR NOT NULL,
            record_id INTEGER NOT NULL,
            value_text TEXT,
            backed_up_at TIMESTAMP DEFAULT now()
        )
        """
    )


def _backup_column(cr, table, column):
    if not _column_exists(cr, table, column):
        _logger.info("  %s.%s does not exist, nothing to back up", table, column)
        return

    cr.execute(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    (data_type,) = cr.fetchone()
    condition = f'"{column}" IS TRUE' if data_type == "boolean" else (
        f'"{column}" IS NOT NULL'
    )
    cr.execute(f'SELECT id, "{column}" FROM "{table}" WHERE {condition}')  # noqa: S608
    rows = cr.fetchall()
    if not rows:
        _logger.info("  %s.%s has no non-default values, nothing to back up", table, column)
        return

    cr.executemany(
        f"""
        INSERT INTO {BACKUP_TABLE} (source_table, source_column, record_id, value_text)
        VALUES (%s, %s, %s, %s)
        """,
        [(table, column, rec_id, str(value)) for rec_id, value in rows],
    )
    _logger.info("  Backed up %s row(s) from %s.%s (l10n_ve_tax, no v19 field)", len(rows), table, column)


def _rename_column(cr, table, old_column, new_column):
    if not _column_exists(cr, table, old_column):
        _logger.info("  %s.%s does not exist, nothing to rename", table, old_column)
        return
    if not _column_exists(cr, table, new_column):
        _logger.warning(
            "  %s.%s exists but target %s.%s does not -- v19 schema not "
            "applied yet or field removed unexpectedly, skipping rename",
            table, old_column, table, new_column,
        )
        return

    # Both columns exist post-schema-init (old one lingers since v19
    # doesn't declare it, new one was just created) -- copy the data
    # across, preferring the old value where the new column is empty,
    # then the old column gets dropped in post-migrate.py.
    cr.execute(
        f'UPDATE "{table}" SET "{new_column}" = "{old_column}" '  # noqa: S608
        f'WHERE "{old_column}" IS NOT NULL AND "{new_column}" IS NOT TRUE'
    )
    _logger.info(
        "  Copied %s row(s) from %s.%s to %s.%s (typo-fix rename)",
        cr.rowcount, table, old_column, table, new_column,
    )


def migrate(cr, version):
    _logger.info(
        "l10n_ve_accountant pre-migrate (19.0.1.0.14): absorbing l10n_ve_tax "
        "(no v19 module of its own)"
    )
    _ensure_backup_table(cr)
    for table, columns in DROPPED_COLUMNS.items():
        for column in columns:
            _backup_column(cr, table, column)
    for table, old_column, new_column in RENAMED_COLUMNS:
        _rename_column(cr, table, old_column, new_column)
    _logger.info("l10n_ve_accountant pre-migrate (19.0.1.0.14) complete")
