"""Pre-migration for l10n_ve_igtf 19.0.1.2.16: explicit field-by-field
report for retiring binaural_advance_payment / binaural_advance_payment_igtf
into the unified l10n_ve_igtf.

Per instruction: migrate data from binaural_advance_payment /
binaural_advance_payment_igtf into l10n_ve_igtf ONLY where l10n_ve_igtf
already declares the same field (same table, same column name -- the
data is already sitting there, nothing to move). Fields that have no
home in l10n_ve_igtf are NOT migrated: they are backed up (so the value
isn't lost outright) and then dropped when the old module is
uninstalled. All views belonging to these two modules are deleted, not
just left to whatever the module uninstall does implicitly.

Full field-by-field comparison (verified by reading both modules' models/
directly, not assumed):

binaural_advance_payment -> l10n_ve_igtf:
  account_move.is_advance_move                                    -> SAME COLUMN, exists in l10n_ve_igtf. No migration needed.
  account_move.origin_payment_advanced_payment_id                 -> SAME COLUMN, exists. No migration needed.
  account_move.invoice_outstanding_credits_debits_widget_advance_payment -> SAME COLUMN, exists. No migration needed.
  account_move.outstanding_credits_debits_widget_advance_payment  -> NOT in l10n_ve_igtf. Binary, NOT store=True (no DB column exists) -- nothing to migrate, no data to lose.
  account_move.cross_move_ids                                     -> NOT in l10n_ve_igtf. Many2many, v19-only (no v17 predecessor in this same module) -- nothing to migrate, table would be empty at migration time regardless.
  account_move_line.payment_id_advance                            -> SAME COLUMN, exists. No migration needed.
  account_payment.is_advance_payment                               -> SAME COLUMN, exists. No migration needed.
  account_payment.advanced_move_ids                                -> SAME relation, exists (One2many, not its own column). No migration needed.
  account_payment.amount_residual_from_payment                    -> NOT in l10n_ve_igtf. Float, real data possible. NOT migrated -- backed up below, then dropped.
  res_company/res_config_settings.advance_customer_account_id      -> SAME COLUMN, exists. No migration needed.
  res_company/res_config_settings.advance_supplier_account_id      -> SAME COLUMN, exists. No migration needed.

binaural_advance_payment_igtf -> l10n_ve_igtf:
  account_move_line.invoice_advance_igtf_id                        -> NOT in l10n_ve_igtf. Many2one, real data possible. NOT migrated -- backed up below, then dropped.
  account_move.igtf_percentage                                     -> NOT in l10n_ve_igtf at the account.move level (l10n_ve_igtf only declares igtf_percentage on account.payment and res.company/res.config.settings, a different model). NOT migrated -- backed up below, then dropped.
  res_company/res_config_settings.advance_payment_igtf_journal_id  -> SAME COLUMN, exists in l10n_ve_igtf. No migration needed.
"""

import logging

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "l10n_ve_igtf_migration_v17_backup"

# Columns exclusive to the modules being retired, with no home in
# l10n_ve_igtf -- backed up here (audit trail), then NOT migrated;
# dropped once the owning module is uninstalled.
EXCLUSIVE_COLUMNS = {
    "account_payment": ["amount_residual_from_payment"],
    "account_move_line": ["invoice_advance_igtf_id"],
    "account_move": [
        "igtf_percentage",
        # l10n_ve_igtf's OWN v17 fields with no v19 equivalent (confirmed
        # absent from l10n_ve_igtf/models/*.py in v19; unrelated to the
        # binaural_advance_payment retirement above, folded in here so
        # every "no field in v19" column for this module lives in one
        # place instead of being spread across several migration folders):
        "amount_paid",
        "alter_igtf_top_aply",
        "foreign_alter_bi_igtf",
    ],
    "res_company": ["igtf_two_percentage_account"],
}

MODULES_TO_RETIRE = [
    "binaural_advance_payment_igtf",
    "binaural_advance_payment",
    # binaural_advance_payment_report: NOT truly deprecated-without-successor
    # -- confirmed by reading both versions' source that it was RENAMED to
    # binaural_account_advance_payment_report (its account_move_line.py
    # payment_ref_id field is byte-for-byte identical, compute+store,
    # already auto-populates correctly once the renamed module is
    # installed -- no data migration needed for it). This OLD-named module
    # still depends on binaural_advance_payment (see its v17 manifest,
    # "depends": ["binaural_account_reports", "binaural_advance_payment"]),
    # which is being retired above -- it can't stay installed regardless.
    # No ir.ui.view records at all (confirmed by grep on its data/*.xml:
    # only ir.actions.client and account.report/account.report.line/
    # account.report.column/account.report.expression config records),
    # so it doesn't need the explicit view-delete treatment the other two
    # modules get -- Odoo's own uninstall cleans up plain ir.model.data
    # records like these without the inherit_id risk views carry.
    "binaural_advance_payment_report",
    # binaural_subsidiary_payment_advance: pure behavior-override module
    # (account_move.py overrides _create_payment_move, no fields declared
    # anywhere, no data of its own to lose). Retired same as
    # binaural_advance_payment -- its own dependency is gone, nothing else
    # in v19 depends on it (grep on every __manifest__.py).
    #
    # NOTE, deliberately NOT here: binaural_subsidiary_payment_advance_igtf
    # (its IGTF-flow sibling). Business decision: that one is KEPT
    # installed, not retired -- its _reconcile_move_with_payment_difference
    # override (propagates account_analytic_id/"sucursal" to the
    # reconciliation move before calling super()) has no equivalent
    # anywhere in l10n_ve_igtf (verified: l10n_ve_igtf's own override of
    # that same method has zero references to account_analytic_id), so
    # dropping it would silently lose subsidiary-tracking on advance
    # payment + IGTF reconciliations. Its manifest depends= was updated
    # from binaural_advance_payment_igtf to l10n_ve_igtf directly (the
    # method it calls super() into now lives there) -- see that module's
    # own __manifest__.py.
    "binaural_subsidiary_payment_advance",
]


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


def _backup_exclusive_columns(cr):
    for table, columns in EXCLUSIVE_COLUMNS.items():
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
                "  Backed up %s row(s) from %s.%s (no field in l10n_ve_igtf to "
                "migrate this into -- will be dropped, not migrated)",
                len(rows), table, column,
            )


def _delete_module_views(cr):
    """Explicitly delete every ir.ui.view (and its ir_model_data entry)
    owned by the two modules being retired, rather than relying only on
    Odoo's own module-uninstall cascade to get to it eventually.

    GUARD: ir.ui.view.inherit_id is ondelete='restrict' in Odoo core -- if
    any other view (most plausibly Studio-created, invisible to a
    source-code check) inherits from one of these, deleting the parent
    raises a foreign-key violation and aborts the whole migration
    transaction. Checked and skipped (with a warning) before attempting
    the delete, instead of finding out the hard way.
    """
    for module_name in MODULES_TO_RETIRE:
        cr.execute(
            "SELECT res_id, name FROM ir_model_data "
            "WHERE module = %s AND model = 'ir.ui.view'",
            (module_name,),
        )
        views = cr.fetchall()
        if not views:
            _logger.info("  No views owned by %s, nothing to delete", module_name)
            continue

        deletable_ids = []
        for view_id, view_name in views:
            cr.execute("SELECT id FROM ir_ui_view WHERE inherit_id = %s", (view_id,))
            children = cr.fetchall()
            if children:
                _logger.warning(
                    "  SKIPPING delete of view %s.%s (id=%s): %s child view(s) "
                    "inherit from it -- deleting would abort on a foreign-key "
                    "violation. Retire/re-parent those first (likely Studio "
                    "customizations), then re-run this migration.",
                    module_name, view_name, view_id, len(children),
                )
                continue
            deletable_ids.append(view_id)

        if deletable_ids:
            cr.execute("DELETE FROM ir_ui_view WHERE id = ANY(%s)", (deletable_ids,))
            cr.execute(
                "DELETE FROM ir_model_data WHERE module = %s AND model = 'ir.ui.view' "
                "AND res_id = ANY(%s)",
                (module_name, deletable_ids),
            )
            _logger.info("  Deleted %s view(s) owned by %s", len(deletable_ids), module_name)


def _mark_modules_to_remove(cr):
    for module_name in MODULES_TO_RETIRE:
        cr.execute("SELECT state FROM ir_module_module WHERE name = %s", (module_name,))
        row = cr.fetchone()
        if not row:
            _logger.info("  Module %s not present in this database, skipping", module_name)
            continue
        if row[0] != "installed":
            _logger.info("  Module %s is in state '%s', not 'installed', skipping", module_name, row[0])
            continue
        cr.execute(
            "UPDATE ir_module_module SET state = 'to remove' WHERE name = %s",
            (module_name,),
        )
        _logger.info("  Marked %s for uninstall", module_name)


def _backfill_is_advance_account(cr):
    """v19 requires account.account.is_advance_account=True for any
    account used as advance_customer_account_id/advance_supplier_account_id
    (new domain on those fields). v17 accounts referenced there never had
    this flag (didn't exist). Without backfilling it, those account
    references carried over from v17 would fail the new domain the next
    time someone opens the field, and any code filtering accounts by
    is_advance_account would silently miss them.
    """
    if not _column_exists(cr, "account_account", "is_advance_account"):
        return

    cr.execute(
        """
        SELECT DISTINCT account_id FROM (
            SELECT advance_customer_account_id AS account_id FROM res_company
            WHERE advance_customer_account_id IS NOT NULL
            UNION
            SELECT advance_supplier_account_id FROM res_company
            WHERE advance_supplier_account_id IS NOT NULL
        ) accounts
        """
    )
    account_ids = [row[0] for row in cr.fetchall()]
    if not account_ids:
        _logger.info("  No advance accounts referenced by any company, nothing to backfill")
        return

    cr.execute(
        "UPDATE account_account SET is_advance_account = TRUE WHERE id = ANY(%s)",
        (account_ids,),
    )
    _logger.info("  Flagged %s account(s) as is_advance_account=TRUE", len(account_ids))


def migrate(cr, version):
    _logger.info(
        "l10n_ve_igtf pre-migrate: retiring binaural_advance_payment / "
        "binaural_advance_payment_igtf -- fields already in l10n_ve_igtf "
        "need no action (same column), exclusive fields are backed up "
        "then dropped (not migrated), and their views are deleted"
    )
    _ensure_backup_table(cr)
    _backup_exclusive_columns(cr)
    _delete_module_views(cr)
    _mark_modules_to_remove(cr)
    _backfill_is_advance_account(cr)
    _logger.info("l10n_ve_igtf pre-migrate (19.0.1.2.16) complete")
