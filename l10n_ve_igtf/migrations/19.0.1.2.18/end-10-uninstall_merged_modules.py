"""Retires the advance payment modules l10n_ve_igtf merges, all together, once there is no way back.

What: marks as 'to remove' the MODULES_TO_RETIRE modules that are installed and every module that
    depends on them, directly or indirectly. Step 5 of Odoo's loading, which runs right after the
    end- scripts, uninstalls them.

Why: the 19.0.1.2.16 pre-migrate already marks them, but in a pre- that does not work. The module
    graph is already built and Odoo loads the ones that come after l10n_ve_igtf anyway; loading
    them puts them back to 'installed' and the mark is lost. Only the ones that Odoo loaded
    before l10n_ve_igtf get retired. The simulation of the Odoo.sh flow on Proalca, without manual
    preparation, ended like this:

      binaural_advance_payment             uninstalled
      binaural_advance_payment_igtf        installed  -> depends on binaural_advance_payment
      binaural_subsidiary_payment_advance  installed  -> depends on binaural_advance_payment

      ERROR Some modules are not loaded, some dependencies or manifest may be missing:
            ['binaural_advance_payment_igtf', 'binaural_subsidiary_payment_advance',
             'binaural_subsidiary_payment_advance_igtf']

    A half-done retirement is worse than none: the ones left installed can never be loaded
    again.

Why in an end-: the end- scripts run once everything has been loaded (step 3.5 of
    odoo/modules/loading.py) and before Odoo uninstalls what is marked (step 5). What is marked
    here cannot be unmarked by anyone. It is the same thing that step 3 of the preparation did by
    hand (08-procedimiento-upgrade-bd.md), which left the reference run run14 with 8 out of 8
    accounting checkpoints exact; the difference is that now it also runs on Odoo.sh, where that
    step does not exist.

Why the dependants too: step 5 uninstalls exactly what is marked. Without marking the whole
    chain, a bridge like binaural_subsidiary_payment_advance_igtf (auto_install) would stay
    installed hanging from an uninstalled module. If a module that is not part of the advance
    payments family shows up in the chain, it is retired anyway —leaving it would be worse—, but
    a warning goes to the log and to the migration report, because that one does need a look.

What is lost: whatever the uninstall deletes from these modules. Their fields that l10n_ve_igtf
    does not declare are already backed up and dropped by 19.0.1.2.16
    (l10n_ve_igtf_migration_v17_backup). What l10n_ve_igtf does declare is not touched: Odoo does
    not delete a record that another installed module also owns.

If it does not run: they stay installed with their dependency uninstalled, and migration-verify
    modulos flags the graph as unhealthy.

How to revert: reinstall the modules. Their exclusive data is recovered from the backup
    table.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)

# The same list as the 19.0.1.2.16 pre-migrate.
MODULES_TO_RETIRE = [
    "binaural_advance_payment_igtf",
    "binaural_advance_payment",
    "binaural_advance_payment_report",
    "binaural_subsidiary_payment_advance",
]

# Dependants known to go out with them: auto_install bridges of the same family.
KNOWN_DEPENDANTS = {"binaural_subsidiary_payment_advance_igtf"}

INSTALLED_STATES = ("installed", "to upgrade", "to install", "to remove")


def migrate(cr, version):
    # Native 19 databases keep these modules: they still ship in integra-addons 19.0.
    if not version or not version.startswith("17."):
        return

    cr.execute(
        """
        WITH RECURSIVE retiro(name) AS (
            SELECT unnest(%s::varchar[])
             UNION
            SELECT m.name
              FROM ir_module_module m
              JOIN ir_module_module_dependency d ON d.module_id = m.id
              JOIN retiro r ON d.name = r.name
        )
        SELECT m.name
          FROM ir_module_module m
          JOIN retiro r ON r.name = m.name
         WHERE m.state IN %s
        """,
        [MODULES_TO_RETIRE, INSTALLED_STATES],
    )
    names = sorted(name for (name,) in cr.fetchall())
    if not names:
        return

    cr.execute("UPDATE ir_module_module SET state = 'to remove' WHERE name IN %s", [tuple(names)])
    _logger.info("Marked for uninstall at the end of the update: %s", ", ".join(names))

    unexpected = sorted(set(names) - set(MODULES_TO_RETIRE) - KNOWN_DEPENDANTS)
    if unexpected:
        msg = (
            "Uninstalled because they depend on the advance payment modules that l10n_ve_igtf "
            "merges: {}. Check that they were not needed.".format(", ".join(unexpected))
        )
        _logger.warning(msg)
        util.add_to_migration_reports(msg, category="Binaural · l10n_ve_igtf")
