"""Pre-migration for l10n_ve_igtf 19.0.1.2.17.

CORRECTION (later audit): this folder originally also included a
MODULES_TO_RETIRE_NO_HOMOLOGADA (binaural_igtf, binaural_base_igtf)
meant for the NON-homologated line. It was removed from here because it
is dead code: for those clients l10n_ve_igtf is ALWAYS a fresh install
(they never had the module), and
odoo/modules/migration.py:151-152 confirms that
migrations/<version>/pre-migrate.py NEVER runs on a fresh install
(state='to install'), only on an upgrade of an already installed module
(state='to upgrade'). That logic was correctly left in
l10n_ve_igtf/__init__.py (pre_init_hook), which does run on a fresh
install -- see that file for the actual coverage of the non-homologated
line. Keeping both copies, here and there, led people to wrongly think
that this file also covers that line.

This folder (HOMOLOGATED line, checkout maintenance-l10nve_17.0)
extends 19.0.1.2.16 with a single real change: RENAMED_COLUMNS fixes
a rename detected in binaural_advance_payment_igtf --
res_company.not_show_bi_igtf_sale_order / not_show_bi_igtf_purchase_order
(with the "_bi_" infix) have no column of the same name in v19 -- v19 has
them WITHOUT the infix: not_show_igtf_sale_order / not_show_igtf_purchase_order
(l10n_ve_igtf/models/res_company.py). It is a rename, not an orphan
column -- it is renamed in place (ALTER TABLE ... RENAME COLUMN), not
backed up and discarded. For the rest (MODULES_TO_RETIRE, EXCLUSIVE_COLUMNS
of binaural_advance_payment/_igtf/_report and
binaural_subsidiary_payment_advance), see 19.0.1.2.16 -- unchanged.
"""

import logging

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "l10n_ve_igtf_migration_v17_backup"

# ============================================================================
# HOMOLOGATED LINE -- unchanged from 19.0.1.2.16
# ============================================================================
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

MODULES_TO_RETIRE = [
    "binaural_advance_payment_igtf",
    "binaural_advance_payment",
    "binaural_advance_payment_report",
    "binaural_subsidiary_payment_advance",
]

# Rename detected in binaural_advance_payment_igtf (affects any client,
# on either of the two lines, that had it installed): the "_bi_" infix
# is not present in the v19 column name.
RENAMED_COLUMNS = [
    ("res_company", "not_show_bi_igtf_sale_order", "not_show_igtf_sale_order"),
    ("res_company", "not_show_bi_igtf_purchase_order", "not_show_igtf_purchase_order"),
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


def _migrate_renamed_columns(cr):
    for table, old_column, new_column in RENAMED_COLUMNS:
        if not _column_exists(cr, table, old_column):
            _logger.info("  %s.%s does not exist, skipping rename", table, old_column)
            continue
        if _column_exists(cr, table, new_column):
            _logger.warning(
                "  Both %s.%s and %s.%s exist -- likely a re-run after a "
                "partial migration. Leaving both columns untouched; resolve "
                "manually.", table, old_column, table, new_column,
            )
            continue
        cr.execute(
            f'ALTER TABLE "{table}" RENAME COLUMN "{old_column}" TO "{new_column}"'  # noqa: S608
        )
        _logger.info("  Renamed %s.%s -> %s.%s", table, old_column, table, new_column)


def _delete_module_views(cr, module_names):
    """Same as in 19.0.1.2.16, reused here for the modules of the
    homologated line (MODULES_TO_RETIRE) -- see that file for the details of
    the inherit_id guard.
    """
    for module_name in module_names:
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


def _mark_modules_to_remove(cr, module_names):
    for module_name in module_names:
        cr.execute("SELECT state FROM ir_module_module WHERE name = %s", (module_name,))
        row = cr.fetchone()
        if not row:
            _logger.info("  Module %s not present in this database, skipping", module_name)
            continue
        # 'to upgrade' counts as installed: during a `-u all` —which is the
        # documented procedure— EVERY installed module is in that state,
        # not in 'installed'. With the original guard the retirement was
        # silently skipped for exactly the modules being upgraded, and they
        # stayed installed with their dependency already uninstalled.
        if row[0] not in ("installed", "to upgrade"):
            _logger.info("  Module %s is in state '%s', not installed, skipping",
                         module_name, row[0])
            continue
        cr.execute(
            "UPDATE ir_module_module SET state = 'to remove' WHERE name = %s",
            (module_name,),
        )
        _logger.info("  Marked %s for uninstall", module_name)


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return

    _logger.info(
        "l10n_ve_igtf pre-migrate (19.0.1.2.17): homologated line "
        "(binaural_advance_payment*) already covered by 19.0.1.2.16, "
        "adds the not_show_bi_igtf_* rename here"
    )
    _ensure_backup_table(cr)
    _backup_exclusive_columns(cr)
    _migrate_renamed_columns(cr)
    _delete_module_views(cr, MODULES_TO_RETIRE)
    _mark_modules_to_remove(cr, MODULES_TO_RETIRE)

    _logger.info("l10n_ve_igtf pre-migrate (19.0.1.2.17) complete")
