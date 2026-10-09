"""Uninstall the Binaural modules that were dropped in v19 without a successor.

What: marks as "to remove" the modules of MODULES_TO_RETIRE that are installed, together with the
    installed modules that depend on them; Odoo uninstalls them at the end of the -u (step 5 of
    load_modules), and their records go with them (views, fields, menus, access rules). Same
    pattern as l10n_ve_igtf 19.0.1.2.18 end-10, which retires the advance payment modules.
    Before that, it copies to l10n_ve_base_migration_v17_backup the values of the retired modules'
    fields (BACKED_UP_FIELDS), because the uninstall drops their columns.

Why: these modules have no module that absorbs them, so their retirement needs a host every
    homologated client has: l10n_ve_base (it depends only on base and web). Leaving them installed
    breaks things in v19 even after their code is gone: binaural_ml adds 5 views to the sale order,
    pricelist rule and stock location forms that use its own fields, and Odoo keeps applying the
    views of a module that is installed but not loaded, so those forms fail. Uninstalling works
    with or without the code on disk: module_uninstall() works from ir_model_data.
    - binaural_base_qr: nobody uses it; the vertical report marks it for removal.
    - binaural_ml: Mercado Libre fields nothing reads in v19, removed from 19.0 in 21b629e13. Two
      are flags (stock_location_ml, pricelist_ml), but sale_order.nickname is free text users fill
      in on the sale order form, so it is backed up before the uninstall.
    - binaural_action_server_pause_meli: depends on meli_oerp_multiple, whose Python dependency is
      not on PyPI; removed from 19.0 in 21b629e13.

    It does not require coming from 17: a database already on 19 that still has one of them
    installed is stranded the same way.

If it does not run: those modules stay installed; binaural_ml breaks the sale order, pricelist and
    location forms once its code is gone.

How to revert: install the module again (while its code exists) and restore its values from
    l10n_ve_base_migration_v17_backup. binaural_base_qr and pause_meli kept no data of their own.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

MODULES_TO_RETIRE = [
    "binaural_base_qr",
    "binaural_ml",
    "binaural_action_server_pause_meli",
]

INSTALLED_STATES = ("installed", "to upgrade", "to install", "to remove")

BACKUP = "l10n_ve_base_migration_v17_backup"

# (module, model, table, column, condition of the rows worth keeping)
BACKED_UP_FIELDS = [
    ("binaural_ml", "sale.order", "sale_order", "nickname",
     "nickname IS NOT NULL AND nickname <> ''"),
    ("binaural_ml", "stock.location", "stock_location", "stock_location_ml",
     "stock_location_ml IS TRUE"),
    ("binaural_ml", "product.pricelist.item", "product_pricelist_item", "pricelist_ml",
     "pricelist_ml IS TRUE"),
]


def _backup_fields(cr, modules, version):
    """Copy the fields of the retired modules before the uninstall drops their columns."""
    fields = [f for f in BACKED_UP_FIELDS if f[0] in modules and util.column_exists(cr, f[2], f[3])]
    if not fields:
        return {}
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
    counts = {}
    for _module, model, table, column, condition in fields:
        cr.execute(
            f"""
            INSERT INTO {BACKUP} (model, res_id, field, value, source_version)
                 SELECT %s, id, %s, {column}::text, %s
                   FROM {table}
                  WHERE {condition}
            ON CONFLICT (model, res_id, field) DO NOTHING
            """,
            [model, column, version],
        )
        counts[f"{table}.{column}"] = cr.rowcount
    return counts


def migrate(cr, version):
    if not version:
        return

    cr.execute(
        """
        WITH RECURSIVE retire(name) AS (
            SELECT unnest(%s::varchar[])
             UNION
            SELECT m.name
              FROM ir_module_module m
              JOIN ir_module_module_dependency d ON d.module_id = m.id
              JOIN retire r ON d.name = r.name
        )
        SELECT m.name
          FROM ir_module_module m
          JOIN retire r ON r.name = m.name
         WHERE m.state IN %s
        """,
        [MODULES_TO_RETIRE, INSTALLED_STATES],
    )
    names = sorted(name for (name,) in cr.fetchall())
    if not names:
        return

    backed_up = _backup_fields(cr, names, version)

    cr.execute("UPDATE ir_module_module SET state = 'to remove' WHERE name IN %s", [tuple(names)])
    _logger.info("Marked to be uninstalled at the end of the update: %s", ", ".join(names))

    dependants = sorted(set(names) - set(MODULES_TO_RETIRE))
    message = "Retired modules (dropped in v19 without a successor), uninstalled: %s." % ", ".join(names)
    if dependants:
        message += " %s are uninstalled because they depend on them: check they were not needed." % ", ".join(
            dependants
        )
    if any(backed_up.values()):
        message += " Their values were backed up in %s: %s." % (
            BACKUP,
            ", ".join("%s %s" % (count, field) for field, count in backed_up.items() if count),
        )
    util.add_to_migration_reports(message, category="Binaural · General")
