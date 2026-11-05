"""Install l10n_ve_account_mf, which takes over part of this module in v19, and back up the pinpad setup.

What:
    1. Marks l10n_ve_account_mf for installation if it is not installed.
    2. Copies to l10n_ve_iot_mf_migration_v17_backup the v17 pinpad and fiscal-device settings
       that no v19 module declares: iot.box.has_pinpad_machine, iot.box.pinpad_port_id and
       iot.device.max_razon_social.

Why:
    1. In v19 res.company.mf_flag_21 (the fiscal printer decimal precision), the fiscal reports
       wizard and wizard.accounting.reports.all_documents moved from this module to
       l10n_ve_account_mf, a module that is new in v19, is not auto_install and is not a
       dependency of this one. Without it nobody declares mf_flag_21: _process_end deletes it
       with its column, and the fiscal printer goes back to the default precision. When
       l10n_ve_account_mf is installed it declares the same field on the same model, so the
       column and the v17 value survive. Same mechanism as binaural_hr_payroll
       19.0.2.11.0/pre-05 (button_install inside a savepoint).
    2. The pinpad (has_pinpad_machine, pinpad_port_id) and max_razon_social are not taken over by
       any v19 module; the ORM deletes them. Product decides whether they come back (D-04).

If it does not run: the fiscal printer loses its decimal-precision setting and the fiscal reports
    disappear from the menu; the pinpad setup is lost without a trace.

How to revert: uninstall l10n_ve_account_mf. The backup changes nothing.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

BACKUP = "l10n_ve_iot_mf_migration_v17_backup"

# (model, table, column, condition)
REMOVED = [
    ("iot.box", "iot_box", "has_pinpad_machine", "IS TRUE"),
    ("iot.box", "iot_box", "pinpad_port_id", "IS NOT NULL"),
    ("iot.device", "iot_device", "max_razon_social", "IS NOT NULL"),
]


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return

    cr.execute("SELECT id FROM ir_module_module WHERE name = 'l10n_ve_account_mf' AND state = 'uninstalled'")
    row = cr.fetchone()
    if row:
        env = util.env(cr)
        try:
            with cr.savepoint():
                env["ir.module.module"].browse(row[0]).button_install()
                env.flush_all()
            util.add_to_migration_reports(
                "Fiscal printer: l10n_ve_account_mf was installed, because in v19 it holds the "
                "printer decimal-precision setting (mf_flag_21) and the fiscal reports that used to "
                "be in l10n_ve_iot_mf.",
                category="Binaural · Sales",
            )
        except Exception as error:  # noqa: BLE001 — reported, the rest of the migration goes on
            _logger.warning("l10n_ve_account_mf could not be marked for installation: %s", error)
            util.add_to_migration_reports(
                f"Fiscal printer: l10n_ve_account_mf could not be installed ({error}). Without it "
                "the printer decimal-precision setting (mf_flag_21) is lost.",
                category="Binaural · Sales",
            )

    cr.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {BACKUP} (
            id serial PRIMARY KEY,
            model varchar NOT NULL,
            res_id integer NOT NULL,
            field varchar NOT NULL,
            value text,
            source_version varchar,
            backed_up_at timestamp NOT NULL DEFAULT (now() at time zone 'UTC'),
            UNIQUE (model, res_id, field)
        )
        """
    )
    backed_up = 0
    for model, table, column, condition in REMOVED:
        if not util.column_exists(cr, table, column):
            continue
        cr.execute(
            f"""
            INSERT INTO {BACKUP} (model, res_id, field, value, source_version)
                 SELECT %s, id, %s, {column}::text, %s
                   FROM {table}
                  WHERE {column} {condition}
            ON CONFLICT (model, res_id, field) DO NOTHING
            """,
            [model, column, version],
        )
        backed_up += cr.rowcount
    if backed_up:
        util.add_to_migration_reports(
            f"IoT: {backed_up} pinpad and fiscal-device settings that v19 no longer has are backed "
            f"up in {BACKUP}.",
            category="Binaural · Sales",
        )
