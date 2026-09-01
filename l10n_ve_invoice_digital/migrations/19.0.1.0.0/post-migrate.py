"""Post-migration for l10n_ve_invoice_digital 19.0.1.0.0.

payment.method.tfhka was a `_name` model owned solely by this module.
Odoo's own upgrade process removes it from ir.model/ir.model.fields once
the module no longer declares it, but does NOT automatically drop the
underlying SQL table -- that's this script's job, now that pre-migrate.py
has backed up every row. Same for the columns that referenced it or
paralleled it (account_journal.payment_method_code, res_currency.code_tfhka,
res_company.dispatch_guide_digital_tfhka, digitalization_with_payment_tfhka).
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

ORPHAN_COLUMNS = {
    "account_journal": ["payment_method_code"],
    "res_currency": ["code_tfhka"],
    "res_company": ["dispatch_guide_digital_tfhka", "digitalization_with_payment_tfhka"],
}

ORPHAN_TABLE = "payment_method_tfhka"


def _views_referencing_field(cr, column):
    """A view (Studio-created, or from a module outside this migration's
    scope) that still has `<field name="column"/>` in its arch will break
    with a "field does not exist" error once the column is gone.
    """
    cr.execute(
        """
        SELECT id, name, model FROM ir_ui_view
        WHERE arch_db::text LIKE %s OR arch_db::text LIKE %s
        """,
        (f'%name="{column}"%', f"%name='{column}'%"),
    )
    return cr.fetchall()


def _drop_orphan_columns(cr):
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


def _drop_orphan_table(cr):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s", (ORPHAN_TABLE,)
    )
    if not cr.fetchone():
        _logger.info("  Table %s does not exist, skipping", ORPHAN_TABLE)
        return

    cr.execute("SELECT id, name FROM ir_ui_view WHERE model = 'payment.method.tfhka'")
    stale_views = cr.fetchall()
    if stale_views:
        _logger.warning(
            "  %s ir.ui.view record(s) still target model payment.method.tfhka "
            "(%s) and will dangle (error on open) once its table is dropped -- "
            "they belong to a model that no longer exists in v19. Not blocking "
            "the table drop for this (unlike field-level references, an "
            "orphaned view for a fully-removed model has nothing to fall back "
            "to), but clean these up manually: %s",
            len(stale_views), ORPHAN_TABLE, stale_views,
        )

    cr.execute(sql.SQL("DROP TABLE {} CASCADE").format(sql.Identifier(ORPHAN_TABLE)))
    _logger.info(
        "  Dropped table %s (data preserved in "
        "l10n_ve_invoice_digital_migration_v17_backup)", ORPHAN_TABLE,
    )


def migrate(cr, version):
    _logger.info("l10n_ve_invoice_digital post-migrate: dropping retired TFHKA catalog/columns")
    _drop_orphan_columns(cr)
    _drop_orphan_table(cr)
    _logger.info("l10n_ve_invoice_digital post-migrate complete")
