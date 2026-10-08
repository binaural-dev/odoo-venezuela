"""Back up the alternate-currency amounts of reconciliations when binaural_account_reports is absent.

What: copies the three alternate-currency amounts of account_partial_reconcile (foreign_amount,
    debit_foreign_amount_currency and credit_foreign_amount_currency) to
    l10n_ve_accountant_migration_v17_backup, only if binaural_account_reports is neither installed
    nor about to be installed.

Why: in v17 this module declares them as stored fields written at reconcile time: they are not
    computed and cannot be rebuilt without the rates of that moment. In v19 they are declared by
    binaural_account_reports (integra-addons).

    - With binaural_account_reports installed nothing is needed: when it loads, the field gets its
      xmlid, and ir.model.data._process_end only removes this module's one.
    - Without it, nobody declares the field in v19: _process_end deletes the ir.model.fields record
      and, with it, the column. Among the v17 databases we have, flr and nomina are in that case.

If it does not run: those clients lose the alternate-currency amounts of every reconciliation. If
    they later install binaural_account_reports on v19, the $ residuals of what was reconciled
    before the migration come out wrong.

How to revert: the backup changes nothing. To recover the amounts, install binaural_account_reports
    and copy them back from the table (source_table = account_partial_reconcile, record_id =
    reconciliation id, source_column = column).

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

from odoo.upgrade import util

BACKUP = "l10n_ve_accountant_migration_v17_backup"
TABLE = "account_partial_reconcile"
COLUMNS = ("foreign_amount", "debit_foreign_amount_currency", "credit_foreign_amount_currency")


def ensure_backup_table(cr):
    # Same schema that 19.0.1.0.13/pre-migrate.py creates, which runs before this script.
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
    # module_installed also counts 'to upgrade' and 'to install'
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
        "Reconciliations: without binaural_account_reports, the alternate-currency amounts of "
        f"account.partial.reconcile are backed up in {BACKUP}: {', '.join(counts) or 'no column present'}.",
        category="Binaural · Accounting",
    )
