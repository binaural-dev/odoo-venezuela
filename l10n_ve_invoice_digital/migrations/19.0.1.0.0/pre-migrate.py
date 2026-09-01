"""Pre-migration for l10n_ve_invoice_digital: v17 -> v19.

v19 dropped the payment.method.tfhka catalog model entirely. In v17,
account.journal.payment_method_code (Many2one) pointed each journal at
a row of that catalog (code + description), and account.move used it
to decide which TFHKA payment-method code to send when digitizing a
document. In v19, get_payment_method() builds that mapping from an
inline dict keyed by payment method NAME (e.g. "Efectivo") instead of
a stored catalog -- there is no field left to receive the old
Many2one, and the catalog table itself disappears with the module
update.

This backs up, before either is dropped:
- The full payment.method.tfhka catalog (id, code, description).
- Which journal pointed at which catalog row
  (account_journal.payment_method_code), so if a journal used a
  non-default code it doesn't just silently vanish.
- res_currency.code_tfhka (per-currency TFHKA code), also gone in v19
  with no replacement field found.
- res_company.dispatch_guide_digital_tfhka /
  digitalization_with_payment_tfhka (Boolean config flags), superseded
  in v19 by invoice_digital_tfhka + the per-picking is_digitalized
  field, but backed up in case the old flags' values need to inform
  how is_digitalized should be backfilled for historical pickings.

NOT something this script can fix: v19 tracks digitization per
stock.picking (is_digitalized, control_number_tfhka), a concept that
did not exist at that granularity in v17 (v17 only had company-wide
config flags). There is no reliable way to derive, from v17 data alone,
which specific historical pickings were "digitized" under the old
flow -- that gap is logged, not silently papered over.
"""

import logging

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "l10n_ve_invoice_digital_migration_v17_backup"


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s", (table,)
    )
    return bool(cr.fetchone())


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
            source_column VARCHAR,
            record_id INTEGER NOT NULL,
            value_text TEXT,
            backed_up_at TIMESTAMP DEFAULT now()
        )
        """
    )


def _backup_payment_method_catalog(cr):
    if not _table_exists(cr, "payment_method_tfhka"):
        _logger.info("  payment_method_tfhka table does not exist, nothing to back up")
        return

    cr.execute("SELECT id, code, description FROM payment_method_tfhka")
    rows = cr.fetchall()
    if not rows:
        _logger.info("  payment_method_tfhka has no rows, nothing to back up")
        return

    cr.executemany(
        f"""
        INSERT INTO {BACKUP_TABLE} (source_table, source_column, record_id, value_text)
        VALUES (%s, %s, %s, %s)
        """,
        [
            ("payment_method_tfhka", "code/description", rec_id, f"{code} | {description}")
            for rec_id, code, description in rows
        ],
    )
    _logger.info("  Backed up %s row(s) of the payment.method.tfhka catalog", len(rows))


def _backup_journal_payment_method_links(cr):
    if not _column_exists(cr, "account_journal", "payment_method_code"):
        _logger.info("  account_journal.payment_method_code does not exist, nothing to back up")
        return
    if not _table_exists(cr, "payment_method_tfhka"):
        cr.execute(
            "SELECT id, payment_method_code FROM account_journal "
            "WHERE payment_method_code IS NOT NULL"
        )
    else:
        cr.execute(
            """
            SELECT aj.id, aj.payment_method_code, pmt.code, pmt.description
            FROM account_journal aj
            JOIN payment_method_tfhka pmt ON pmt.id = aj.payment_method_code
            """
        )
    rows = cr.fetchall()
    if not rows:
        _logger.info("  No journal has payment_method_code set, nothing to back up")
        return

    cr.executemany(
        f"""
        INSERT INTO {BACKUP_TABLE} (source_table, source_column, record_id, value_text)
        VALUES (%s, %s, %s, %s)
        """,
        [(("account_journal", "payment_method_code", row[0], str(row[1:]))) for row in rows],
    )
    _logger.info("  Backed up %s journal->payment_method_tfhka link(s)", len(rows))


def _backup_simple_column(cr, table, column):
    if not _column_exists(cr, table, column):
        _logger.info("  %s.%s does not exist, nothing to back up", table, column)
        return

    cr.execute(
        f'SELECT id, "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL'  # noqa: S608
    )
    rows = cr.fetchall()
    if not rows:
        _logger.info("  %s.%s has no non-null values, nothing to back up", table, column)
        return

    cr.executemany(
        f"""
        INSERT INTO {BACKUP_TABLE} (source_table, source_column, record_id, value_text)
        VALUES (%s, %s, %s, %s)
        """,
        [(table, column, rec_id, str(value)) for rec_id, value in rows],
    )
    _logger.info("  Backed up %s row(s) from %s.%s", len(rows), table, column)


def migrate(cr, version):
    _logger.info("l10n_ve_invoice_digital pre-migrate: backing up retired TFHKA catalog/config")
    _ensure_backup_table(cr)
    _backup_payment_method_catalog(cr)
    _backup_journal_payment_method_links(cr)
    _backup_simple_column(cr, "res_currency", "code_tfhka")
    _backup_simple_column(cr, "res_company", "dispatch_guide_digital_tfhka")
    _backup_simple_column(cr, "res_company", "digitalization_with_payment_tfhka")
    _logger.warning(
        "l10n_ve_invoice_digital pre-migrate: v19 tracks digitization per "
        "stock.picking (is_digitalized/control_number_tfhka), a concept that "
        "did not exist in v17 (only company-wide flags did). Historical "
        "pickings will come out of this migration with is_digitalized=False "
        "regardless of whether they were actually sent to TFHKA under the "
        "old flow -- there is no v17 data to derive that from per-picking."
    )
