"""Post-migration for l10n_ve_donation 19.0.2.0.3.

Drops stock_scrap.donation_reason (v17 column, ya migrado a tags por
pre-migrate.py de esta misma carpeta).

res_company.account_stock_journal_id NO SE ELIMINA (a propósito,
distinto del resto de columnas huérfanas de este proyecto): verificado
que NO es un rename hacia donation_account_id -- son conceptos
distintos (account_stock_journal_id apunta a account.journal,
donation_account_id a account.account, para un propósito diferente).
Es un campo genuinamente ausente en cualquier modelo v19 (ningún
módulo lo declara), pero el CÓDIGO de v19 sigue leyéndolo por atributo
en DOS lugares:
  - l10n_ve_donation/models/stock_move.py
    (_create_account_move: "journal_id": ...company_id.account_stock_journal_id.id)
  - integra-addons/binaural_subsidiary_stock/models/stock_move.py:132
    (mismo patrón exacto)
Ambos son bugs de código v19 (AttributeError garantizado al primer
scrap de donación/subsidiaria que dispare esa línea), no algo que una
migración de datos deba resolver -- pero justamente por eso NO se
elimina la columna: hacerlo perdería el dato de configuración del
cliente (qué diario usar) antes de que el equipo de desarrollo decida
cómo re-exponer el campo (o reescribir esas dos líneas para derivar el
diario de otra forma). Se deja la columna intacta -- ya se respaldó
igual en pre-migrate.py, por si acaso, pero el dato real sigue vivo en
res_company.account_stock_journal_id.
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

    _logger.warning(
        "l10n_ve_donation post-migrate: res_company.account_stock_journal_id "
        "se DEJA intacta a propósito -- l10n_ve_donation/models/stock_move.py Y "
        "binaural_subsidiary_stock/models/stock_move.py todavía la leen por "
        "atributo (bug de código v19 en ambos módulos, no de esta migración). "
        "No borrar hasta que el equipo de desarrollo corrija esas dos líneas o "
        "reexponga el campo. Ver MIGRATION_NOTES_donation.md."
    )
