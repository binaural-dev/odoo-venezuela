"""Post-migration for l10n_ve_igtf 19.0.1.2.17.

Nothing to do here: 19.0.1.2.16/post-migrate.py already drops
EXCLUSIVE_COLUMNS (same columns, unchanged in this version) and that
version always runs before this one in the same -u. The only change in
19.0.1.2.17 is the pre-migrate.py rename (RENAMED_COLUMNS), which does
not need any post-migrate step.

(See the docstring of pre-migrate.py in this same folder: the section
for the retirement of binaural_igtf/binaural_base_igtf for the
non-homologated line that originally lived here was moved to
l10n_ve_igtf/__init__.py -- pre_init_hook -- because this file never
runs on a fresh install of a module.)
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return

    _logger.info("l10n_ve_igtf post-migrate (19.0.1.2.17): no additional actions")
