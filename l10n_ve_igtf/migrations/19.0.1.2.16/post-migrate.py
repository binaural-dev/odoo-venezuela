"""Post-migration for l10n_ve_igtf 19.0.1.2.16.

Drops the columns exclusive to binaural_advance_payment /
binaural_advance_payment_igtf (no field in l10n_ve_igtf to receive them),
already backed up by pre-migrate.py. Everything else those two modules
declared shares a column name with l10n_ve_igtf, so it needed no action
at all -- the data was already in place.
"""

import logging

from psycopg2 import sql
from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# Los cuatro campos que en v19 pasaron a compute+store con compute_bi_igtf.
IGTF_COMPUTED_FIELDS = ["bi_igtf", "igtf_top_aply", "alter_bi_igtf", "foreign_bi_igtf"]

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


def _views_referencing_field(cr, column):
    cr.execute(
        """
        SELECT id, name, model FROM ir_ui_view
        WHERE arch_db::text LIKE %s OR arch_db::text LIKE %s
        """,
        (f'%name="{column}"%', f"%name='{column}'%"),
    )
    return cr.fetchall()


def _recompute_bi_igtf(cr):
    """account_move.bi_igtf/igtf_top_aply/alter_bi_igtf/foreign_bi_igtf eran
    campos de asignacion directa en v17; en v19 son compute+store con una
    formula reescrita (compute_bi_igtf). Los valores crudos que vienen de v17
    no son confiables bajo la formula nueva, asi que hay que recomputarlos.

    Esta version llamaba a recalculate_bi_igtf(), que **no existe en v19** --
    ni en l10n_ve_igtf ni en ningun otro addon del arbol. El resultado era que
    las 303 tandas fallaban con AttributeError, el guion lo tragaba con un
    try/except y la migracion terminaba "bien" **sin haber recomputado nada**:

        AttributeError: 'account.move' object has no attribute 'recalculate_bi_igtf'

    Se recomputa con util.recompute_fields, que es el metodo del proyecto
    (ADR-001): trocea solo, decide entre flush y commit segun el volumen, y
    reporta progreso. Y si un campo no existe, falla en vez de tragarselo.

    Ojo: el server action "Fix Venezuela BI IGTF Invoices"
    (l10n_ve_igtf/data/ir_actions_server.xml) llama a ese mismo metodo
    inexistente, igual que binaural_advance_payment_igtf/models/account_move.py.
    Los dos siguen rotos en runtime; eso es del vertical, no de esta migracion.
    """
    util.recompute_fields(cr, "account.move", IGTF_COMPUTED_FIELDS, logger=_logger)


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

    for module_name in ["binaural_advance_payment_igtf", "binaural_advance_payment"]:
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

    _logger.info("l10n_ve_igtf post-migrate: recomputing IGTF fields under the v19 formula")
    _recompute_bi_igtf(cr)

    _logger.info("l10n_ve_igtf post-migrate (19.0.1.2.16) complete")
