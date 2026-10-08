from . import models
from . import wizard

import logging

_logger = logging.getLogger(__name__)

BACKUP_TABLE = "l10n_ve_igtf_migration_v17_backup"

# ============================================================================
# NON-HOMOLOGATED LINE -- l10n_ve_igtf is a FRESH install for these
# clients (they never had l10n_ve_igtf, they had binaural_igtf/
# binaural_base_igtf). The pre/post-migrate.py files under migrations/ do
# NOT run on a fresh module install (Odoo only runs them when the module
# was already installed and moves to 'to upgrade' -- confirmed in
# odoo/modules/migration.py:151-152), so this retirement -- which in
# migrations/19.0.1.2.16 and 19.0.1.2.17 assumed an upgrade -- is
# repeated here in an init hook, which does run on a fresh install.
#
# It covers ALL the advance payments/IGTF modules that a non-homologated
# client may have installed (confirmed by the inventory:
# binaural_base_igtf depends on binaural_advance_payment, and
# binaural_advance_payment_igtf is auto_install on top of binaural_igtf +
# binaural_advance_payment -- so these modules, "homologated" by name,
# may also be present in the non-homologated line).
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

RENAMED_COLUMNS = [
    ("res_company", "not_show_bi_igtf_sale_order", "not_show_igtf_sale_order"),
    ("res_company", "not_show_bi_igtf_purchase_order", "not_show_igtf_purchase_order"),
]

MODULES_TO_RETIRE = [
    "binaural_advance_payment_igtf",
    "binaural_advance_payment",
    "binaural_advance_payment_report",
    "binaural_subsidiary_payment_advance",
    "binaural_igtf",
    "binaural_base_igtf",
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


def _backup_and_drop_exclusive_columns(cr):
    for table, columns in EXCLUSIVE_COLUMNS.items():
        for column in columns:
            if not _column_exists(cr, table, column):
                continue

            cr.execute(
                f'SELECT id, "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL'  # noqa: S608
            )
            rows = cr.fetchall()
            if rows:
                cr.executemany(
                    f"""
                    INSERT INTO {BACKUP_TABLE} (source_table, source_column, record_id, value_text)
                    VALUES (%s, %s, %s, %s)
                    """,
                    [(table, column, rec_id, str(value)) for rec_id, value in rows],
                )
                _logger.info("  Backed up %s row(s) from %s.%s", len(rows), table, column)

            # At this point (pre_init_hook, before l10n_ve_igtf creates
            # its own schema) the column is exclusively owned by a
            # binaural_* module that is still installed -- it can be
            # dropped directly, there is no risk of an _auto_init of
            # l10n_ve_igtf recreating it because that module does not
            # declare this field.
            cr.execute(f'ALTER TABLE "{table}" DROP COLUMN "{column}"')  # noqa: S608
            _logger.info("  Dropped column %s.%s", table, column)


def _migrate_renamed_columns(cr):
    for table, old_column, new_column in RENAMED_COLUMNS:
        if not _column_exists(cr, table, old_column):
            continue
        if _column_exists(cr, table, new_column):
            continue
        cr.execute(
            f'ALTER TABLE "{table}" RENAME COLUMN "{old_column}" TO "{new_column}"'  # noqa: S608
        )
        _logger.info("  Renamed %s.%s -> %s.%s", table, old_column, table, new_column)


def _delete_module_views(cr, module_names):
    for module_name in module_names:
        cr.execute(
            "SELECT res_id, name FROM ir_model_data "
            "WHERE module = %s AND model = 'ir.ui.view'",
            (module_name,),
        )
        views = cr.fetchall()
        deletable_ids = []
        for view_id, view_name in views:
            cr.execute("SELECT id FROM ir_ui_view WHERE inherit_id = %s", (view_id,))
            if cr.fetchall():
                _logger.warning(
                    "  SKIPPING delete of view %s.%s (id=%s): it has child views.",
                    module_name, view_name, view_id,
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
        cr.execute(
            "UPDATE ir_module_module SET state = 'to remove' "
            "WHERE name = %s AND state = 'installed'",
            (module_name,),
        )


def pre_init_hook(env):
    cr = env.cr
    _logger.info(
        "l10n_ve_igtf pre_init_hook: retiring binaural_igtf/"
        "binaural_base_igtf/binaural_advance_payment* (non-homologated "
        "line, fresh install)"
    )
    _ensure_backup_table(cr)
    _backup_and_drop_exclusive_columns(cr)
    _migrate_renamed_columns(cr)
    _delete_module_views(cr, MODULES_TO_RETIRE)
    _mark_modules_to_remove(cr, MODULES_TO_RETIRE)
