"""Post-migration for l10n_ve_igtf 19.0.1.2.17.

Complemento de 19.0.1.2.16 para la línea NO homologada -- ver el
docstring de pre-migrate.py en esta misma carpeta para el detalle del
hallazgo (columnas huérfanas de binaural_igtf/binaural_base_igtf que el
script anterior no cubría porque esos módulos no estaban en
MODULES_TO_RETIRE).

Reprocesa el drop de EXCLUSIVE_COLUMNS -- es idempotente (chequea
existencia de columna antes de actuar), así que si 19.0.1.2.16 ya corrió
sobre esta base (línea homologada) esto no hace nada nuevo; si en cambio
la base viene de la línea no homologada y 19.0.1.2.16 dejó las columnas
sin poder dropearse limpiamente (porque el módulo dueño seguía
instalado), este post-migrate corre DESPUÉS de que pre-migrate.py de
esta misma versión marcó binaural_igtf/binaural_base_igtf como
'to remove' -- para cuando este post-migrate corre, el módulo ya no
declara el campo activamente en el registro (aunque el estado en
ir_module_module siga en 'to remove' hasta el final del -u, igual que
documenta 19.0.1.2.16).
"""

import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

EXCLUSIVE_COLUMNS = {
    "account_payment": ["amount_residual_from_payment"],
    "account_move_line": ["invoice_advance_igtf_id"],
    "account_move": [
        "igtf_percentage",
        "amount_paid",
        "alter_igtf_top_aply",
        "foreign_alter_bi_igtf",
    ],
    "res_company": ["igtf_two_percentage_account"],
}

MODULES_TO_RETIRE_NO_HOMOLOGADA = [
    "binaural_igtf",
    "binaural_base_igtf",
]


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
    for table, columns in EXCLUSIVE_COLUMNS.items():
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
                    "in their arch. Views: %s. Fix/retire those views first; "
                    "safe to re-run this migration afterward.",
                    table, col, len(views), views,
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
                "  Dropped column %s.%s (not migrated -- no field in "
                "l10n_ve_igtf receives it; value preserved in "
                "l10n_ve_igtf_migration_v17_backup)", table, col,
            )

    for module_name in MODULES_TO_RETIRE_NO_HOMOLOGADA:
        cr.execute("SELECT state FROM ir_module_module WHERE name = %s", (module_name,))
        row = cr.fetchone()
        if row and row[0] not in ("uninstalled",):
            _logger.info(
                "  %s is in state '%s' at the end of this run -- Odoo's "
                "end-of-upgrade pass uninstalls 'to remove' modules AFTER "
                "every module's own migrations finish, so this is expected "
                "here, not a failure. Verify with a fresh query after the "
                "full -u completes.", module_name, row[0],
            )

    _logger.info("l10n_ve_igtf post-migrate (19.0.1.2.17) complete")
