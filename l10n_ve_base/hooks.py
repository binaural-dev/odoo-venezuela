from odoo.exceptions import UserError

from .migrations import _common

RERUN_MESSAGE = (
    "This database comes from the v17 operativa line (binaural_* base modules, no odoo-venezuela). "
    "Its modules were just turned into their l10n_ve_* successors, and the change is saved, but "
    "this update was already planned as a fresh install of them. Run the update again: it will "
    "upgrade them with their migration scripts. To do it in a single run, pass "
    "--pre-upgrade-scripts=<odoo-venezuela>/l10n_ve_base/upgrade_scripts/"
    "pre-10-operative_to_homologated.py to the update."
)


def pre_init_hook(env):
    """Stop a database of the v17 operativa line from getting l10n_ve_* installed from scratch.

    This module is only installed from scratch on a database that never had odoo-venezuela. If
    that database has the binaural_* base modules of the v17 operativa line, the pre-upgrade
    script did not run and Odoo is about to install every l10n_ve_* module on top of their data,
    without their migration scripts. The module graph of this update cannot be changed any more,
    so the database is converted, the conversion is saved, and the update is stopped: the next
    run upgrades the successors as on a homologated database.

    On a database born in 19, or one from the homologated line, there is nothing to convert and
    the install goes on.
    """
    if not _common.legacy_modules(env.cr):
        return
    _common.convert(env.cr)
    env.cr.commit()
    raise UserError(RERUN_MESSAGE)
