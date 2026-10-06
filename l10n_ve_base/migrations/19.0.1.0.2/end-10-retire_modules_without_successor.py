"""Uninstall the Binaural modules that were dropped in v19 without a successor.

What: marks as "to remove" the modules of MODULES_TO_RETIRE that are installed, together with the
    installed modules that depend on them; Odoo uninstalls them at the end of the -u (step 5 of
    load_modules), and their records go with them (views, fields, menus, access rules). Same
    pattern as l10n_ve_igtf 19.0.1.2.18 end-10, which retires the advance payment modules.

Why: these modules have no module that absorbs them, so their retirement needs a host every
    homologated client has: l10n_ve_base (it depends only on base and web). Leaving them installed
    breaks things in v19 even after their code is gone: binaural_ml adds 5 views to the sale order,
    pricelist rule and stock location forms that use its own fields, and Odoo keeps applying the
    views of a module that is installed but not loaded, so those forms fail. Uninstalling works
    with or without the code on disk: module_uninstall() works from ir_model_data.
    - binaural_base_qr: nobody uses it; the vertical report marks it for removal.
    - binaural_ml: Mercado Libre flags nothing reads; removed from 19.0 in 21b629e13.
    - binaural_action_server_pause_meli: depends on meli_oerp_multiple, whose Python dependency is
      not on PyPI; removed from 19.0 in 21b629e13.

    It does not require coming from 17: a database already on 19 that still has one of them
    installed is stranded the same way.

If it does not run: those modules stay installed; binaural_ml breaks the sale order, pricelist and
    location forms once its code is gone.

How to revert: install the module again (while its code exists). binaural_ml only kept flags nothing
    reads; binaural_base_qr and pause_meli kept no data of their own.

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

    cr.execute("UPDATE ir_module_module SET state = 'to remove' WHERE name IN %s", [tuple(names)])
    _logger.info("Marked to be uninstalled at the end of the update: %s", ", ".join(names))

    dependants = sorted(set(names) - set(MODULES_TO_RETIRE))
    message = "Retired modules (dropped in v19 without a successor), uninstalled: %s." % ", ".join(names)
    if dependants:
        message += " %s are uninstalled because they depend on them: check they were not needed." % ", ".join(
            dependants
        )
    util.add_to_migration_reports(message, category="Binaural · General")
