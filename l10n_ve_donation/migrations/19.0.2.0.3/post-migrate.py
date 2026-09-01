"""Post-migration for l10n_ve_donation 19.0.2.0.3.

Drops the two v17 columns already backed up (and, for donation_reason,
already best-effort migrated to tags) by pre-migrate.py.
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

ORPHAN_COLUMNS = {
    "stock_scrap": ["donation_reason"],
    "res_company": ["account_stock_journal_id"],
}


def _views_referencing_field(cr, column):
    cr.execute(
        """
        SELECT id, name, model FROM ir_ui_view
        WHERE arch_db::text LIKE %s OR arch_db::text LIKE %s
        """,
        (f'%name="{column}"%', f"%name='{column}'%"),
    )
    return cr.fetchall()


def migrate(cr, version):
    for table, columns in ORPHAN_COLUMNS.items():
        tbl = sql.Identifier(table)
        for col in columns:
            cr.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s AND column_name = %s",
                (table, col),
            )
            if not cr.fetchone():
                _logger.info("  Column %s.%s does not exist, skipping", table, col)
                continue

            views = _views_referencing_field(cr, col)
            if views:
                _logger.warning(
                    "  SKIPPING drop of %s.%s: %s view(s) still reference it "
                    "in their arch -- would break them. Views: %s. Fix/retire "
                    "those views first; safe to re-run this migration "
                    "afterward.", table, col, len(views), views,
                )
                continue

            col_id = sql.Identifier(col)
            cr.execute(
                "SELECT constraint_name FROM information_schema.table_constraints "
                "WHERE table_name = %s AND constraint_type = 'FOREIGN KEY'",
                (table,),
            )
            for (fk_name,) in cr.fetchall():
                cr.execute(
                    "SELECT 1 FROM information_schema.constraint_column_usage "
                    "WHERE constraint_name = %s AND column_name = %s",
                    (fk_name, col),
                )
                if cr.fetchone():
                    cr.execute(
                        sql.SQL("ALTER TABLE {} DROP CONSTRAINT {}").format(
                            tbl, sql.Identifier(fk_name)
                        )
                    )
                    _logger.info("    Dropped FK %s on %s.%s", fk_name, table, col)

            cr.execute(sql.SQL("ALTER TABLE {} DROP COLUMN {}").format(tbl, col_id))
            _logger.info("  Dropped column %s.%s", table, col)

    _logger.warning(
        "l10n_ve_donation post-migrate: reminder -- res_company.account_stock_journal_id "
        "is gone, but v19's stock_move.py still reads it for donation scraps. Fix the "
        "v19 module code (not a migration script) before donation flows go live. See "
        "MIGRATION_NOTES_donation.md."
    )
