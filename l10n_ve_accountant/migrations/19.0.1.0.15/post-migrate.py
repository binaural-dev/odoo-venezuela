"""Post-migration for l10n_ve_accountant 19.0.1.0.15.

Elimina res_company.module_binaural_igtf (línea no homologada, ver
pre-migrate.py en esta misma carpeta), con el mismo guard de vistas que
19.0.1.0.13/19.0.1.0.14 usan para el resto de columnas huérfanas.
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

ORPHAN_COLUMNS_NO_HOMOLOGADA = {
    "res_company": ["module_binaural_igtf"],
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
    for table, columns in ORPHAN_COLUMNS_NO_HOMOLOGADA.items():
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
                    "in their arch: %s. Fix/retire those views first; safe "
                    "to re-run this migration afterward.",
                    table, col, len(views), views,
                )
                continue

            cr.execute(sql.SQL("ALTER TABLE {} DROP COLUMN {}").format(tbl, sql.Identifier(col)))
            _logger.info(
                "  Dropped column %s.%s (propio de binaural_tax, sin "
                "campo en l10n_ve_accountant; valor preservado en "
                "l10n_ve_accountant_migration_v17_backup)", table, col,
            )

    _logger.info("l10n_ve_accountant post-migrate (19.0.1.0.15) complete")
