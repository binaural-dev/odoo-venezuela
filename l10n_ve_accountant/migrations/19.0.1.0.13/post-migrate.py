"""Post-migration for l10n_ve_accountant 19.0.1.0.13.

Drops the columns already backed up by pre-migrate.py -- v19 declares no
field for them. Guards each drop against views that might still
reference the field (Studio, or a module outside this migration) so we
don't break a working view; those get skipped and logged instead.
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

ORPHAN_COLUMNS = {
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
            _logger.info(
                "  Dropped column %s.%s (values preserved in "
                "l10n_ve_accountant_migration_v17_backup)", table, col,
            )

    _logger.info("l10n_ve_accountant post-migrate complete")
