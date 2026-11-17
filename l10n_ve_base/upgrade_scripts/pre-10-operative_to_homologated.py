"""Turn the modules of the v17 operativa line into their l10n_ve_* successors, before any module loads.

What: renames every binaural_* base module of the v17 operativa line (integra-addons 17.0, no
    odoo-venezuela) to the l10n_ve_* module that replaced it, moves its records with it, copies
    the v17 fiscal flags that binaural_operative translates, and backs up the fields only that
    line had. The whole logic, and what each step is for, is in migrations/_common.py.

Why: those modules do not exist in 19. Without this, Odoo installs every l10n_ve_* module from
    scratch on top of their data, and none of the 17 to 19 migration scripts run. With it, the
    update sees the successors as installed in 17 and upgrades them, exactly as on a database of
    the homologated line.

How to run it: it is not in a migrations/ folder on purpose. It has to run before Odoo builds
    the module graph, and the only place for that is a pre-upgrade script:

        odoo -d <database> -u all --stop-after-init \\
            --pre-upgrade-scripts=<odoo-venezuela>/l10n_ve_base/upgrade_scripts/pre-10-operative_to_homologated.py

    Where that option cannot be passed, the pre-init hook of l10n_ve_base does the same
    conversion and asks for the update to be run a second time.

If it does not run: see hooks.py. A database of the operativa line never gets l10n_ve_*
    installed from scratch any more.

It does nothing on a database born in 19 or one from the homologated line.

How to revert: restore the database. The backed up fields are in
    l10n_ve_base_migration_v17_backup, and the v17 flags in the binaural_v17_* tables.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

from odoo.exceptions import UserError
from odoo.tools import config

from odoo.addons.l10n_ve_base.migrations import _common


def migrate(cr, version):
    if not _common.legacy_modules(cr):
        return
    # -u all is stored as {'base': True}: only an update of base walks every installed module,
    # which is what the reset below relies on. With -u <module> the converted successors would be
    # loaded without being upgraded, on their v16/v17 schema; stop before converting anything.
    if "base" not in config["update"]:
        raise UserError(
            "This database comes from the operativa line: run this script with -u all "
            "(or -u base), not with a list of modules."
        )
    _common.convert(cr)
    _common.reset_upgrade_states(cr)
