"""Post-migration for l10n_ve_donation 19.0.2.0.3.

Drops stock_scrap.donation_reason (v17 column, already migrated to tags by
pre-migrate.py in this same folder).

res_company.account_stock_journal_id IS NOT DROPPED -- and it is not an
orphan column at all: it is an Odoo CORE field
(stock_account/models/res_company.py, same name, same purpose).
The reason l10n_ve_donation/models/stock_move.py could not find it
was not that the field was missing in v19, but that
l10n_ve_donation did not declare "stock_account" as a dependency in its
manifest -- fixed in this same commit (__manifest__.py). With that
dependency added, the core field is available without having to
declare anything new (no field is created, only the missing dependency
is fixed), and the physical column that already exists in
res_company is reused as is -- there is nothing to migrate or to
drop.

Note on a correction from this same session:
integra-addons/binaural_subsidiary_stock/models/stock_move.py had also
been flagged as affected by the same problem -- FALSE POSITIVE, discarded:
that module DOES depend on "stock_account" in its __manifest__.py, so
it never had the problem.
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

ORPHAN_COLUMNS = {
    "stock_scrap": ["donation_reason"],
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

    _logger.info(
        "l10n_ve_donation post-migrate: res_company.account_stock_journal_id is kept "
        "on purpose: it is the core stock_account field, read by "
        "l10n_ve_donation/models/stock_move.py and "
        "binaural_subsidiary_stock/models/stock_move.py. "
        "See MIGRATION_NOTES_donation.md."
    )
