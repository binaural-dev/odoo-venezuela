"""Install binaural_operative on a database of the operativa line, in the same update.

What: when the database had binaural_fiscal (convert() left its fiscal flag in
    binaural_v17_journal_fiscal), marks binaural_operative to be installed, with its dependencies
    and its auto_install bridges. Odoo installs it later in this same update, once every installed
    module is loaded, and its pre-init hook turns the flag into is_operative on every journal:
    fiscal False (or NULL) -> operative, fiscal True -> standard. The logic is
    _common.install_operative_module.

Why: the fiscal / non-fiscal split of the v16/v17 journals is binaural_operative in 19, but nothing
    installed it: it is not auto_install and no module of the operativa line depends on it. The
    flag stayed in the snapshot and every journal came out standard; castic_19_operativo needed a
    manual install. It runs in post- of this module, not in the pre-upgrade script, because by
    then the module list is updated (the pre-upgrade script runs before it, when
    binaural_operative may not be listed yet) and the ORM can mark its dependencies.
    util.force_install_module is not used: during a -u all it only records the module for the
    Odoo upgrade service and installs nothing.

If it does not run: binaural_operative stays uninstalled and every journal standard; the flag
    waits in binaural_v17_journal_fiscal until someone installs it by hand.

How to revert: uninstall binaural_operative. The flag is kept in
    binaural_v17_journal_fiscal_applied.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

from odoo.addons.l10n_ve_base.migrations import _common

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    lines = _common.install_operative_module(util.env(cr))
    if not lines:
        return
    message = "l10n_ve_base, binaural_operative:\n- " + "\n- ".join(lines)
    _logger.warning(message)
    util.add_to_migration_reports(message, category="Binaural · General")
