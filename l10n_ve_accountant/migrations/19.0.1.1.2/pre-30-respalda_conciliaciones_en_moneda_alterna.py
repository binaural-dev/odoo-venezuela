"""Respalda los montos en moneda alterna de las conciliaciones cuando binaural_account_reports no está.

Qué: copia a l10n_ve_accountant_migration_v17_backup los tres montos en moneda alterna de
    account_partial_reconcile (foreign_amount, debit_foreign_amount_currency y
    credit_foreign_amount_currency), sólo si binaural_account_reports no está instalado ni por
    instalarse.

Por qué: en 17 los declara este módulo como campos almacenados que se escriben al conciliar: no son
    calculados y no se pueden reconstruir sin las tasas del momento. En 19 los declara
    binaural_account_reports (integra-addons).

    - Con binaural_account_reports instalado no hace falta nada: al cargarlo, el campo gana su
      xmlid, e ir.model.data._process_end sólo borra el de este módulo.
    - Sin él, nadie declara el campo en 19: _process_end borra el ir.model.fields y, con él, la
      columna. De las bases v17 que tenemos, flr y nomina están en ese caso.

Qué pasa si no corre: en esos clientes se pierden los montos en moneda alterna de todas las
    conciliaciones. Si después instalan binaural_account_reports en 19, los residuales en $ de lo
    conciliado antes de migrar salen mal.

Cómo revertirlo: el respaldo no toca nada. Para recuperar los montos, instalar
    binaural_account_reports y copiarlos de vuelta desde la tabla (source_table = account_partial_reconcile,
    record_id = id de la conciliación, source_column = columna).

Tarea: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

from odoo.upgrade import util

BACKUP = "l10n_ve_accountant_migration_v17_backup"
TABLE = "account_partial_reconcile"
COLUMNS = ("foreign_amount", "debit_foreign_amount_currency", "credit_foreign_amount_currency")


def ensure_backup_table(cr):
    # Mismo esquema que crea 19.0.1.0.13/pre-migrate.py, que corre antes que este script.
    cr.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {BACKUP} (
            id SERIAL PRIMARY KEY,
            source_table VARCHAR NOT NULL,
            source_column VARCHAR NOT NULL,
            record_id INTEGER NOT NULL,
            value_text TEXT,
            backed_up_at TIMESTAMP DEFAULT now()
        )
        """
    )


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return
    # module_installed también cuenta 'to upgrade' y 'to install'
    if util.module_installed(cr, "binaural_account_reports"):
        return

    ensure_backup_table(cr)
    counts = []
    for column in COLUMNS:
        if not util.column_exists(cr, TABLE, column):
            continue
        cr.execute(
            f"""
            INSERT INTO {BACKUP} (source_table, source_column, record_id, value_text)
                 SELECT %s, %s, t.id, t.{column}::text
                   FROM {TABLE} t
                  WHERE t.{column} IS NOT NULL AND t.{column} <> 0
                    AND NOT EXISTS (
                        SELECT 1 FROM {BACKUP} b
                         WHERE b.source_table = %s AND b.source_column = %s AND b.record_id = t.id
                    )
            """,
            [TABLE, column, TABLE, column],
        )
        counts.append(f"{column} {cr.rowcount}")

    util.add_to_migration_reports(
        "Conciliaciones: sin binaural_account_reports, los montos en moneda alterna de "
        f"account.partial.reconcile quedan respaldados en {BACKUP}: {', '.join(counts) or 'ninguna columna presente'}.",
        category="Binaural · Contabilidad",
    )
