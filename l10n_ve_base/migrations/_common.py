"""Turn a database of the v17 operativa line into what the homologated line left behind.

The v17 operativa line (integra-addons 17.0) never had odoo-venezuela: its Venezuelan base lives
in binaural_* modules, the ancestors of the l10n_ve_* ones. Those modules do not exist in 19, so
on a plain -u all Odoo installs every l10n_ve_* module from scratch on top of their data: their
migrations/ never run (they only run on an upgrade), the install loads the data files ignoring
noupdate, and the post-init hooks run as on an empty database.

convert() avoids all that by renaming each binaural_* module to its l10n_ve_* successor before
the module graph is built. Odoo then sees the successor as installed in 17 and upgrades it, with
the same migrations/ scripts a client of the homologated line (l10nve_17.0) gets.

What it does, in order:

- SNAPSHOTS: copies the v17 fiscal flag of the journals and the POS receipts to plain tables,
  which is where binaural_operative and binaural_operative_pos read them from. Their columns
  belong to binaural_fiscal and binaural_pos, and are dropped later in the same update.
- BACKED_UP_FIELDS: copies to BACKUP_TABLE the values of the fields that only the operativa
  line had and that 19 does not declare, because Odoo drops their columns at the end of the
  update. Each entry is (legacy module, model, table, column, condition of the rows to keep).
- RENAMED_MODULES: moves every record of the legacy module to its successor. The views of the
  legacy module are removed first (the successor recreates the ones 19 declares), since a v17
  view that 19 no longer declares aborts the update. Where the successor is already installed,
  the legacy module is merged into it instead.
- XMLID_RENAMES: renames the data records whose identifier carries the legacy module name, so
  that the successor updates them instead of creating a duplicate.
- l10n_ve_base is registered as installed in 17, as it is on every homologated database, so
  that its own migrations/ run too.

The modules of the operativa line that have no successor are retired by
migrations/19.0.1.0.3/end-10, once every module is loaded. binaural_operative, which turns the
fiscal flag into is_operative, is marked to be installed by migrations/19.0.1.0.4/post-10
(install_operative_module), once the module list is updated.

It is meant to run from a pre-upgrade script (upgrade_scripts/pre-10-operative_to_homologated.py,
through --pre-upgrade-scripts), before Odoo loads any module. The pre-init hook of this module
is the fallback: there the graph is already built, so it converts the database and asks for the
update to be run again.
"""

import logging

from odoo.tools.sql import column_exists, table_exists

_logger = logging.getLogger(__name__)

INSTALLED_STATES = ("installed", "to upgrade")
PLACEHOLDER_STATES = ("uninstalled", "uninstallable", "to install")

BASE_MODULE = "l10n_ve_base"
BASE_V17_VERSION = "17.0.0.0.0"

BACKUP_TABLE = "l10n_ve_base_migration_v17_backup"

RENAMED_MODULES = (
    ("binaural_location", "l10n_ve_location"),
    ("binaural_filter_partner", "l10n_ve_filter_partner"),
    ("binaural_rate", "l10n_ve_rate"),
    ("binaural_currency_rate_live", "l10n_ve_currency_rate_live"),
    ("binaural_contact", "l10n_ve_contact"),
    ("binaural_accountant", "l10n_ve_accountant"),
    ("binaural_tax", "l10n_ve_tax"),
    ("binaural_tax_payer", "l10n_ve_tax_payer"),
    ("binaural_invoice", "l10n_ve_invoice"),
    ("binaural_ref_bank", "l10n_ve_ref_bank"),
    ("binaural_payment_extension", "l10n_ve_payment_extension"),
    ("binaural_igtf", "l10n_ve_igtf"),
    ("binaural_base_igtf", "l10n_ve_igtf"),
    ("binaural_account_fiscalyear_closing", "l10n_ve_account_fiscalyear_closing"),
    ("binaural_stock", "l10n_ve_stock"),
    ("binaural_sale", "l10n_ve_sale"),
    ("binaural_iot_mf", "l10n_ve_iot_mf"),
    ("binaural_pos", "l10n_ve_pos"),
    ("binaural_pos_mf", "l10n_ve_pos_mf"),
    ("binaural_pos_igtf", "l10n_ve_pos_igtf"),
)

MODULES_RETIRED_ALONE = (
    # The root of the operativa line: many modules depend on it (binaural_margin, binaural_mrp,
    # binaural_sitef_base...), some may be absent from the addons path during the update and keep
    # their old dependency. Retiring it in cascade would uninstall them and drop their tables, so
    # it is only retired when nothing installed depends on it.
    "binaural_base",
)

MODULES_WITHOUT_SUCCESSOR = (
    "binaural_fiscal",
    "binaural_fiscal_inspector",
    "binaural_fiscal_inspector_delivery",
    "binaural_fiscal_inspector_pos",
    "binaural_groups_chatter",
    "binaural_stock_purchase",
)

XMLID_RENAMES = {
    "binaural_invoice": {
        "action_invoice_free_form_binaural_invoice": "action_invoice_free_form_l10n_ve_invoice",
    },
    "binaural_payment_extension": {
        "access_binaural_account_retention": "access_l10n_ve_account_retention",
        "access_binaural_account_retention_1": "access_l10n_ve_account_retention_1",
        "access_binaural_account_retention_2": "access_l10n_ve_account_retention_2",
        "access_binaural_account_retention_3": "access_l10n_ve_account_retention_3",
        "access_binaural_account_retention_line": "access_l10n_ve_account_retention_line",
        "access_binaural_account_retention_line_1": "access_l10n_ve_account_retention_line_1",
        "access_binaural_account_retention_line_2": "access_l10n_ve_account_retention_line_2",
        "access_binaural_account_retention_line_3": "access_l10n_ve_account_retention_line_3",
        "action_payment_concept_binaural_payment_extension": "action_payment_concept_l10n_ve_payment_extension",
        "fees_retention_data_substrat_binaural_payment_extension": "fees_retention_data_substrat_l10n_ve_payment_extension",
        "fees_retention_data_percentage_one_binaural_payment_extension": "fees_retention_data_percentage_one_l10n_ve_payment_extension",
        "fees_retention_data_percentage_two_binaural_payment_extension": "fees_retention_data_percentage_two_l10n_ve_payment_extension",
        "fees_retention_data_substrat_second_binaural_payment_extension": "fees_retention_data_substrat_second_l10n_ve_payment_extension",
        "fees_retention_data_binaural_percentage_three_payment_extension": "fees_retention_data_l10n_ve_percentage_three_payment_extension",
        "fees_retention_data_percentage_four_binaural_payment_extension": "fees_retention_data_percentage_four_l10n_ve_payment_extension",
        "fees_retention_data_percentage_five_binaural_payment_extension": "fees_retention_data_percentage_five_l10n_ve_payment_extension",
        "type_person_binaural_payment_extension": "type_person_l10n_ve_payment_extension",
        "type_person_two_binaural_payment_extension": "type_person_two_l10n_ve_payment_extension",
        "type_person_three_binaural_payment_extension": "type_person_three_l10n_ve_payment_extension",
        "type_person_four_binaural_payment_extension": "type_person_four_l10n_ve_payment_extension",
        "type_person_five_binaural_payment_extension": "type_person_five_l10n_ve_payment_extension",
        "type_person_six_binaural_payment_extension": "type_person_six_l10n_ve_payment_extension",
        "type_person_seven_binaural_payment_extension": "type_person_seven_l10n_ve_payment_extension",
        "payment_concept_one_binaural_payment_extension": "payment_concept_one_l10n_ve_payment_extension",
        "payment_concept_two_binaural_payment_extension": "payment_concept_two_l10n_ve_payment_extension",
        "payment_concept_three_binaural_payment_extension": "payment_concept_three_l10n_ve_payment_extension",
        "payment_concept_four_binaural_payment_extension": "payment_concept_four_l10n_ve_payment_extension",
        "payment_concept_five_binaural_payment_extension": "payment_concept_five_l10n_ve_payment_extension",
        "payment_concept_six_binaural_payment_extension": "payment_concept_six_l10n_ve_payment_extension",
        "payment_concept_seven_binaural_payment_extension": "payment_concept_seven_l10n_ve_payment_extension",
    },
}

SHARED_XMLIDS = (
    ("l10n_ve_payment_extension", "tax_unit_data_binaural_payment_extension",
     "l10n_ve_accountant", "tax_unit_data_l10n_ve_payment_extension"),
)

SNAPSHOTS = (
    ("binaural_v17_journal_fiscal", "account_journal", "id AS journal_id, fiscal",
     "fiscal", ("binaural_fiscal", "field_account_journal__fiscal")),
    ("binaural_v17_pos_order_receipt", "pos_order", "id, to_receipt",
     "to_receipt", ("binaural_pos", "field_pos_order__to_receipt")),
    ("binaural_v17_pos_config_receipt", "pos_config", "id, receipt_journal_id",
     "receipt_journal_id", ("binaural_pos", "field_pos_config__receipt_journal_id")),
)

BACKED_UP_FIELDS = (
    ("binaural_tax", "res.company", "res_company", "module_binaural_igtf",
     "module_binaural_igtf IS TRUE"),
    ("binaural_payment_extension", "account.retention.line", "account_retention_line", "active",
     "active IS NOT TRUE"),
    ("binaural_igtf", "account.journal", "account_journal", "default_is_igtf_config",
     "default_is_igtf_config IS TRUE"),
    ("binaural_igtf", "account.payment", "account_payment", "is_igtf", "is_igtf IS TRUE"),
    ("binaural_igtf", "account.payment", "account_payment", "amount_residual_from_payment",
     "COALESCE(amount_residual_from_payment, 0) <> 0"),
    ("binaural_base_igtf", "account.move", "account_move", "amount_to_pay_igtf",
     "COALESCE(amount_to_pay_igtf, 0) <> 0"),
    ("binaural_base_igtf", "account.move", "account_move", "payment_igtf_id",
     "payment_igtf_id IS NOT NULL"),
    ("binaural_base_igtf", "res.company", "res_company", "igtf_account_expense",
     "igtf_account_expense IS NOT NULL"),
    ("binaural_base_igtf", "res.company", "res_company", "journal_igtf_expense",
     "journal_igtf_expense IS NOT NULL"),
    ("binaural_account_fiscalyear_closing", "account.fiscalyear.closing",
     "account_fiscalyear_closing", "journal_type", "journal_type IS DISTINCT FROM 'all'"),
    ("binaural_stock", "res.company", "res_company",
     "not_allow_internal_transfers_without_enough_quantities",
     "not_allow_internal_transfers_without_enough_quantities IS TRUE"),
    ("binaural_stock", "res.company", "res_company",
     "not_allow_sale_picking_lines_without_enough_quantities",
     "not_allow_sale_picking_lines_without_enough_quantities IS TRUE"),
    ("binaural_pos", "pos.config", "pos_config", "always_invoice", "always_invoice IS TRUE"),
    ("binaural_pos", "pos.config", "pos_config", "keep_journal", "keep_journal IS TRUE"),
    ("binaural_pos", "res.company", "res_company", "pos_tax_inside", "pos_tax_inside IS TRUE"),
    ("binaural_pos_mf", "pos.config", "pos_config", "iface_fiscal_data_module",
     "iface_fiscal_data_module IS NOT NULL"),
    ("binaural_pos_igtf", "pos.config", "pos_config", "apply_igtf", "apply_igtf IS TRUE"),
    ("binaural_stock_purchase", "purchase.order.line", "purchase_order_line",
     "liters_per_unit_total", "COALESCE(liters_per_unit_total, 0) <> 0"),
    ("binaural_stock_purchase", "stock.picking", "stock_picking", "purchase_order_id",
     "purchase_order_id IS NOT NULL"),
)


def legacy_modules(cr, renamed_modules=RENAMED_MODULES):
    """Return the modules of the v17 operativa line that are installed, with their version."""
    names = tuple(old for old, _new in renamed_modules)
    if not names:
        return {}
    cr.execute(
        "SELECT name, latest_version FROM ir_module_module WHERE name IN %s AND state IN %s",
        [names, INSTALLED_STATES],
    )
    return dict(cr.fetchall())


def backup_fields(cr, modules, version, backed_up_fields=BACKED_UP_FIELDS):
    """Copy to BACKUP_TABLE the fields of the given modules that the update is about to drop.

    Returns the number of values copied, by table.column.
    """
    fields = [
        field for field in backed_up_fields
        if field[0] in modules and column_exists(cr, field[2], field[3])
    ]
    if not fields:
        return {}
    cr.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {BACKUP_TABLE} (
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
    counts = {}
    for _module, model, table, column, condition in fields:
        cr.execute(
            f"""
            INSERT INTO {BACKUP_TABLE} (model, res_id, field, value, source_version)
                 SELECT %s, id, %s, "{column}"::text, %s
                   FROM "{table}"
                  WHERE {condition}
            ON CONFLICT (model, res_id, field) DO NOTHING
            """,
            [model, column, version],
        )
        if cr.rowcount:
            counts[f"{table}.{column}"] = cr.rowcount
    return counts


def take_snapshots(cr, snapshots=SNAPSHOTS):
    """Copy the v17 flags that binaural_operative and binaural_operative_pos translate.

    A snapshot taken before the version jump is kept as it is. The legacy column only counts
    next to the record its module registered for it, so that a 19 field of the same name is
    never taken for v17 data. Returns the tables created.
    """
    created = []
    for table, source, columns, column, (module, xmlid) in snapshots:
        if table_exists(cr, table) or table_exists(cr, table + "_applied"):
            continue
        if not (table_exists(cr, source) and column_exists(cr, source, column)):
            continue
        cr.execute(
            "SELECT 1 FROM ir_model_data WHERE module = %s AND name = %s", [module, xmlid]
        )
        if not cr.rowcount:
            continue
        cr.execute(f'CREATE TABLE "{table}" AS SELECT {columns} FROM "{source}"')
        created.append(table)
    return created


def missing_snapshots(cr, snapshots=SNAPSHOTS):
    """Return the snapshots that are missing although their module is installed.

    It happens when the legacy column did not survive the version jump and no copy was taken on
    the v17 database: the flag is lost, and whoever runs the migration has to know.
    """
    missing = []
    for table, _source, _columns, _column, (module, _xmlid) in snapshots:
        if table_exists(cr, table) or table_exists(cr, table + "_applied"):
            continue
        cr.execute(
            "SELECT 1 FROM ir_module_module WHERE name = %s AND state IN %s",
            [module, INSTALLED_STATES],
        )
        if cr.rowcount:
            missing.append(table)
    return missing


def _remove_views(cr, module):
    """Remove the views a legacy module owns. Returns how many, and the custom ones disabled.

    A view made by a user on top of one of them cannot outlive it, and is disabled instead of
    removed: it is reported so that it can be rebuilt on the 19 view.
    """
    from odoo.upgrade import util

    cr.execute(
        "SELECT res_id FROM ir_model_data WHERE module = %s AND model = 'ir.ui.view'", [module]
    )
    view_ids = [row[0] for row in cr.fetchall()]
    if not view_ids:
        return 0, []
    cr.execute(
        """
        WITH RECURSIVE tree(id) AS (
            SELECT id FROM ir_ui_view WHERE inherit_id IN %s
             UNION
            SELECT child.id FROM ir_ui_view child JOIN tree ON child.inherit_id = tree.id
        )
        SELECT view.name
          FROM ir_ui_view view
          JOIN tree ON tree.id = view.id
         WHERE NOT EXISTS (
                   SELECT 1 FROM ir_model_data data
                    WHERE data.model = 'ir.ui.view' AND data.res_id = view.id
                      AND data.module != 'studio_customization'
               )
        """,
        [tuple(view_ids)],
    )
    custom = [row[0] for row in cr.fetchall()]
    for view_id in view_ids:
        cr.execute("SELECT 1 FROM ir_ui_view WHERE id = %s", [view_id])
        if cr.rowcount:
            util.remove_view(cr, view_id=view_id, silent=True)
    return len(view_ids), custom


def _drop_placeholder(cr, module_id):
    """Delete the row Odoo keeps for a module that was never installed."""
    cr.execute("DELETE FROM ir_module_module_dependency WHERE module_id = %s", [module_id])
    cr.execute(
        "DELETE FROM ir_model_data WHERE model = 'ir.module.module' AND res_id = %s", [module_id]
    )
    cr.execute("DELETE FROM ir_module_module WHERE id = %s", [module_id])


def _move_records(cr, old, new):
    """Hand every record of the legacy module over to its successor.

    A legacy identifier whose name the successor already has is dropped: the successor keeps
    its own record.
    """
    cr.execute(
        """
        DELETE FROM ir_model_data legacy
              USING ir_model_data successor
              WHERE legacy.module = %s
                AND successor.module = %s
                AND successor.name = legacy.name
        """,
        [old, new],
    )
    cr.execute("UPDATE ir_model_data SET module = %s WHERE module = %s", [new, old])
    cr.execute(
        """
        UPDATE ir_module_module_dependency dependency
           SET name = %s
         WHERE name = %s
           AND NOT EXISTS (
                   SELECT 1 FROM ir_module_module_dependency other
                    WHERE other.module_id = dependency.module_id AND other.name = %s
               )
        """,
        [new, old, new],
    )
    cr.execute("DELETE FROM ir_module_module_dependency WHERE name = %s", [old])


def _adopt_module(cr, old, new):
    """Rename the legacy module to its successor, or merge it when the successor is installed.

    Returns "renamed" or "merged".
    """
    cr.execute("SELECT id, state FROM ir_module_module WHERE name = %s", [new])
    successor = cr.fetchone()
    if successor and successor[1] in PLACEHOLDER_STATES:
        _drop_placeholder(cr, successor[0])
        successor = None
    _move_records(cr, old, new)
    cr.execute("SELECT id FROM ir_module_module WHERE name = %s", [old])
    (old_id,) = cr.fetchone()
    if successor:
        _drop_placeholder(cr, old_id)
        cr.execute(
            "UPDATE ir_module_module SET state = 'to upgrade' WHERE id = %s AND state = 'installed'",
            [successor[0]],
        )
        return "merged"
    # The migrations of the l10n_ve_* successors only act when they come from 17
    # (version.startswith("17.")): a module of the v16 operativa line would skip them all and,
    # for instance, get invoice_date_display filled with the day of the update. It is registered
    # as installed in 17, as register_base_module does with l10n_ve_base.
    cr.execute(
        """
        UPDATE ir_module_module
           SET name = %s, state = 'to upgrade',
               latest_version = CASE WHEN latest_version LIKE '16.%%' THEN %s ELSE latest_version END
         WHERE id = %s
        """,
        [new, BASE_V17_VERSION, old_id],
    )
    cr.execute(
        """
        UPDATE ir_model_data
           SET name = %s
         WHERE module = 'base' AND model = 'ir.module.module' AND res_id = %s
        """,
        ["module_" + new, old_id],
    )
    return "renamed"


def _rename_xmlids(cr, module, renames):
    """Rename the identifiers of a module, unless the new name is already taken."""
    renamed = 0
    for old_name, new_name in renames.items():
        cr.execute(
            """
            UPDATE ir_model_data data
               SET name = %s
             WHERE module = %s
               AND name = %s
               AND NOT EXISTS (
                       SELECT 1 FROM ir_model_data other
                        WHERE other.module = data.module AND other.name = %s
                   )
            """,
            [new_name, module, old_name, new_name],
        )
        renamed += cr.rowcount
    return renamed


def _share_xmlids(cr, shared_xmlids=SHARED_XMLIDS):
    """Give a second identifier to the records two modules of 19 declare under different names.

    Without it, the second module creates its own copy of the record.
    """
    for module, name, other_module, other_name in shared_xmlids:
        cr.execute(
            """
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                 SELECT %s, %s, model, res_id, true
                   FROM ir_model_data
                  WHERE module = %s AND name = %s
            ON CONFLICT DO NOTHING
            """,
            [other_module, other_name, module, name],
        )


def register_base_module(cr):
    """Register l10n_ve_base as installed in 17, so that Odoo upgrades it instead of installing it.

    Every homologated database has it installed, and its migrations/ are where the modules
    without a successor are retired.
    """
    cr.execute("SELECT id, state FROM ir_module_module WHERE name = %s", [BASE_MODULE])
    row = cr.fetchone()
    if row and row[1] not in PLACEHOLDER_STATES:
        return False
    if row:
        cr.execute(
            "UPDATE ir_module_module SET state = 'to upgrade', latest_version = %s WHERE id = %s",
            [BASE_V17_VERSION, row[0]],
        )
        return True
    cr.execute(
        """
        INSERT INTO ir_module_module (name, state, latest_version, auto_install, demo)
             VALUES (%s, 'to upgrade', %s, false, false)
          RETURNING id
        """,
        [BASE_MODULE, BASE_V17_VERSION],
    )
    (module_id,) = cr.fetchone()
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
             VALUES ('base', %s, 'ir.module.module', %s, true)
        """,
        ["module_" + BASE_MODULE, module_id],
    )
    return True


def convert(cr, renamed_modules=RENAMED_MODULES, xmlid_renames=None):
    """Convert a database of the v17 operativa line, if it is one. Returns the report lines.

    It does nothing on a database without modules of that line: one born in 19, or one that
    comes from the homologated line.
    """
    if xmlid_renames is None:
        xmlid_renames = XMLID_RENAMES
    installed = legacy_modules(cr, renamed_modules)
    if not installed:
        return []

    lines = []
    snapshots = take_snapshots(cr)
    if snapshots:
        lines.append("v17 flags copied for binaural_operative: %s." % ", ".join(snapshots))

    missing = missing_snapshots(cr)
    if missing:
        lines.append(
            "MISSING v17 flags, their columns did not survive and no copy was taken on the v17 "
            "database, so binaural_operative cannot translate them: %s." % ", ".join(missing)
        )

    version = max(installed.values(), key=lambda value: value or "")
    backed_up = backup_fields(cr, set(installed) | set(MODULES_WITHOUT_SUCCESSOR), version)
    if backed_up:
        lines.append(
            "Fields only the operativa line had, backed up in %s before the update drops them: %s."
            % (BACKUP_TABLE, ", ".join("%s %s" % (count, field) for field, count in backed_up.items()))
        )

    adopted, views, custom_views = [], 0, []
    for old, new in renamed_modules:
        if old not in installed:
            continue
        removed, custom = _remove_views(cr, old)
        views += removed
        custom_views += custom
        outcome = _adopt_module(cr, old, new)
        _rename_xmlids(cr, new, xmlid_renames.get(old, {}))
        adopted.append("%s -> %s (%s)" % (old, new, outcome))
    _share_xmlids(cr)
    register_base_module(cr)

    lines.append(
        "Modules of the v17 operativa line turned into their homologated successors, which are "
        "now upgraded as on a homologated database: %s." % ", ".join(adopted)
    )
    if views:
        lines.append(
            "%s views of those modules removed; the successors recreate the ones 19 declares." % views
        )
    if custom_views:
        lines.append(
            "Custom views built on top of them, now disabled; rebuild them on the 19 views: %s."
            % ", ".join(sorted(set(custom_views)))
        )
    message = "l10n_ve_base, from the v17 operativa line:\n- " + "\n- ".join(lines)
    _logger.warning(message)
    try:
        from odoo.upgrade import util
    except ImportError:
        return lines
    util.add_to_migration_reports(message, category="Binaural · General")
    return lines


def reset_upgrade_states(cr):
    """Leave 'installed' the modules the Odoo upgrade service hands over 'to upgrade'. Returns how many.

    On -u all, Odoo marks the new dependencies of 19 to be installed (account_invoice_pricelist
    for l10n_ve_accountant, l10n_ve_purchase for binaural_purchase...) through button_upgrade on
    base, which only walks the 'installed' modules: the ones already 'to upgrade' never get them,
    and every module that needs them is skipped. Leaving them 'installed', as Odoo itself does
    after a failed update, lets button_upgrade, which runs right after the pre-upgrade scripts,
    mark them again together with their new dependencies. Only valid when base is updated (-u
    all): the pre-upgrade script checks it before calling this.
    """
    cr.execute(
        "UPDATE ir_module_module SET state = 'installed' WHERE state = 'to upgrade' AND name != 'base'"
    )
    _logger.info("%s modules 'to upgrade' left 'installed' for button_upgrade", cr.rowcount)
    return cr.rowcount


OPERATIVE_MODULE = "binaural_operative"
JOURNAL_FISCAL_SNAPSHOT = SNAPSHOTS[0][0]


def install_operative_module(env, module=OPERATIVE_MODULE):
    """Mark binaural_operative to be installed on a database of the operativa line. Returns the report lines.

    The v16/v17 fiscal / non-fiscal split of the journals (binaural_fiscal) is binaural_operative
    in 19, but nothing installs it: it is not auto_install and no module of the operativa line
    depends on it. convert() only copies the flag to JOURNAL_FISCAL_SNAPSHOT, which is what
    binaural_operative translates into is_operative from its pre-init hook. Marking it here, with
    button_install so that its dependencies and its auto_install bridges come along, makes Odoo
    install it later in the same update, once every installed module is loaded.

    Only a database that had binaural_fiscal has the snapshot, so nothing happens on a database of
    the homologated line or one born in 19. Neither if the module is not in the addons path (a
    project without integra-addons): then the report says so.
    """
    cr = env.cr
    if not table_exists(cr, JOURNAL_FISCAL_SNAPSHOT):
        return []
    record = env["ir.module.module"].search([("name", "=", module)])
    if not record:
        return [
            "%s is not in the addons path: the v16/v17 fiscal flag of the journals stays in %s "
            "until it is installed." % (module, JOURNAL_FISCAL_SNAPSHOT)
        ]
    if record.state != "uninstalled":
        return []
    from odoo.exceptions import UserError

    cr.execute("SELECT name FROM ir_module_module WHERE state = 'to install'")
    already = {name for (name,) in cr.fetchall()}
    # button_install marks the dependencies before it checks exclusions and may raise halfway:
    # without the savepoint, the modules marked so far would be installed anyway.
    env.flush_all()
    try:
        with cr.savepoint():
            record.button_install()
            env.flush_all()
    except UserError as error:
        env.invalidate_all()
        return [
            "%s could not be marked to be installed, install it by hand to translate the "
            "v16/v17 fiscal flag of the journals: %s" % (module, error)
        ]
    cr.execute("SELECT name FROM ir_module_module WHERE state = 'to install' ORDER BY name")
    names = [name for (name,) in cr.fetchall() if name not in already]
    return [
        "%s marked to be installed in this update, to turn the v16/v17 fiscal flag of the "
        "journals into is_operative: %s." % (module, ", ".join(names))
    ]
