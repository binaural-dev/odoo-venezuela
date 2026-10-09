"""Pre-migration for l10n_ve_invoice: v17 -> v19.

res_company.mandatory_contact_in_payable_or_receivable_accounting_accounts
is gone in v19 -- not a rename (block_invoice_display_date_upper_than_date,
which sits in the same spot in res_company.py, is an unrelated feature).
We migrate VALUES, not old validation behavior: back up who had it set
(cheap, in case anyone asks later) and let post-migrate.py drop the column.

ir_sequence.code, also flagged as "gone" during the initial repo scan, is a
false alarm: it's a core Odoo field on ir.sequence, not owned by this
module -- no action needed.
"""

import logging

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "l10n_ve_invoice_migration_v17_backup"
FLAG_COLUMN = "mandatory_contact_in_payable_or_receivable_accounting_accounts"


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    if not _column_exists(cr, "res_company", FLAG_COLUMN):
        _logger.info("l10n_ve_invoice pre-migrate: %s does not exist, nothing to do", FLAG_COLUMN)
        return

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

    cr.execute(f'SELECT id FROM res_company WHERE "{FLAG_COLUMN}" IS TRUE')  # noqa: S608
    enabled_companies = cr.fetchall()
    if enabled_companies:
        cr.executemany(
            f"""
            INSERT INTO {BACKUP_TABLE} (source_table, source_column, record_id, value_text)
            VALUES ('res_company', %s, %s, 'True')
            """,
            [(FLAG_COLUMN, rec_id) for (rec_id,) in enabled_companies],
        )
    _logger.info(
        "l10n_ve_invoice pre-migrate: backed up %s compan%s that had %s "
        "enabled (no v19 equivalent) before it's dropped",
        len(enabled_companies), "y" if len(enabled_companies) == 1 else "ies", FLAG_COLUMN,
    )
