"""Reassign ir_model_data entries from binaural_filter_partner to l10n_ve_filter_partner on
an upgrade of a base that already has l10n_ve_filter_partner installed.

pre_init_hook (see l10n_ve_filter_partner/__init__.py) only runs when this module is being
installed for the first time (update_operation == 'install'). A base that already has
l10n_ve_filter_partner installed with rows still orphaned under the legacy module name only
goes through an 'upgrade' operation, which does not call pre_init_hook -- this migration
script is the complementary hook Odoo provides for that path
(odoo/modules/loading.py: migrations 'pre' scripts run for update_operation == 'upgrade').

Reuses the exact same reassignment function as pre_init_hook so the logic isn't duplicated.
"""

from odoo.addons.l10n_ve_filter_partner import reassign_filter_partner_data_ids


def migrate(cr, version):
    reassign_filter_partner_data_ids(cr)
