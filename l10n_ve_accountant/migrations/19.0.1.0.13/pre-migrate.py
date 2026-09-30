"""Pre-migration for l10n_ve_accountant: v17 -> v19.

SIMPLIFIED (confirmed by the business: every real client being migrated
is already VEF-base -- there is no USD-primary-company scenario to
rebase). This replaces the earlier version of this script, which built
an elaborate USD<->VEF currency-role swap for a scenario that does not
apply to any actual deployment. That swap logic (and its two rounds of
adversarial audit) is preserved in migrations/19.0.1.0.12/ for the
record, but is not run here -- this version does ONLY what was asked:
migrate data field-to-field, and call out fields with no v19 home.

Fields confirmed to have NO v19 equivalent at all (grep-verified against
integra_19/odoo-venezuela/l10n_ve_accountant/models/*.py -- absent from
that module, and from every other v19 module too):

- account_move.is_reset_to_draft_for_price_change (Boolean flag)
- account_move.foreign_inverse_rate_vef (Float, compute+store in v17)
- account_move_line.foreign_price_manual (Boolean)
- account_move_line.foreign_debit_no_format (Float)
- account_move_line.foreign_credit_no_format (Float)

Everything else on these models (debit, credit, balance, price_unit,
foreign_debit, foreign_credit, foreign_balance, foreign_price,
foreign_rate, foreign_inverse_rate, real_portion_amount,
amount_residual, amount_residual_currency, and all account.partial.reconcile
fields) exists under the SAME column name in v19 -- same table, same
column, so the data is already exactly where it needs to be. No value
is recalculated or moved between fields.
"""

import logging

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "l10n_ve_accountant_migration_v17_backup"

DEPRECATED_COLUMNS = {
    "account_move": [
        "is_reset_to_draft_for_price_change",
        "foreign_inverse_rate_vef",
    ],
    "account_move_line": [
        "foreign_price_manual",
        "foreign_debit_no_format",
        "foreign_credit_no_format",
    ],
}


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
        f'"{column}" IS NOT NULL AND "{column}" != 0'
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
    _logger.info("  Backed up %s row(s) from %s.%s", len(rows), table, column)


def migrate(cr, version):
    _logger.info("l10n_ve_accountant pre-migrate: backing up fields with no v19 equivalent")
    _ensure_backup_table(cr)
    for table, columns in DEPRECATED_COLUMNS.items():
        for column in columns:
            _backup_column(cr, table, column)
    _logger.info("l10n_ve_accountant pre-migrate complete")
