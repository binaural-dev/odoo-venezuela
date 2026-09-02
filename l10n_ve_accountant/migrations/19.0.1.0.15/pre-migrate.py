"""Pre-migration for l10n_ve_accountant 19.0.1.0.15.

============================================================================
LÍNEA NO HOMOLOGADA (rama 17.0 de integra-addons, sin odoo-venezuela)
============================================================================
Del inventario campo por campo de binaural_tax (ver
INVENTARIO_MODULOS_NO_HOMOLOGADOS.md): 19.0.1.0.14 ya cubre la absorción
de l10n_ve_tax hacia l10n_ve_accountant, y por coincidencia de esquema
(mismos nombres de tabla/columna) esa migración también procesa
correctamente los campos equivalentes de binaural_tax -- EXCEPTO uno que
19.0.1.0.14 no contemplaba porque no existe en l10n_ve_tax:
res_company.module_binaural_igtf (Boolean, declarado directamente en
binaural_tax, sin campo equivalente en l10n_ve_accountant v19). Se
respalda y elimina aquí, siguiendo el mismo patrón que 19.0.1.0.14.

No hay nada que hacer para la línea homologada en esta versión -- ese
campo no existe en l10n_ve_tax v17 (el módulo que 19.0.1.0.14 ya cubrió).
"""

import logging

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "l10n_ve_accountant_migration_v17_backup"

# ============================================================================
# LÍNEA NO HOMOLOGADA -- nuevo en 19.0.1.0.15
# ============================================================================
ORPHAN_COLUMNS_NO_HOMOLOGADA = {
    "res_company": ["module_binaural_igtf"],
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


def _backup_orphan_columns(cr):
    for table, columns in ORPHAN_COLUMNS_NO_HOMOLOGADA.items():
        for column in columns:
            if not _column_exists(cr, table, column):
                _logger.info("  %s.%s does not exist, nothing to back up", table, column)
                continue

            cr.execute(
                f'SELECT id, "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL'  # noqa: S608
            )
            rows = cr.fetchall()
            if not rows:
                _logger.info("  %s.%s has no non-null values, nothing to back up", table, column)
                continue

            cr.executemany(
                f"""
                INSERT INTO {BACKUP_TABLE} (source_table, source_column, record_id, value_text)
                VALUES (%s, %s, %s, %s)
                """,
                [(table, column, rec_id, str(value)) for rec_id, value in rows],
            )
            _logger.info(
                "  Backed up %s row(s) from %s.%s (propio de binaural_tax, "
                "sin campo en l10n_ve_accountant -- se elimina, no se migra)",
                len(rows), table, column,
            )


def migrate(cr, version):
    _logger.info(
        "l10n_ve_accountant pre-migrate (19.0.1.0.15): respaldando "
        "res_company.module_binaural_igtf (línea no homologada, propio "
        "de binaural_tax, sin equivalente en v19)"
    )
    _ensure_backup_table(cr)
    _backup_orphan_columns(cr)
    _logger.info("l10n_ve_accountant pre-migrate (19.0.1.0.15) complete")
