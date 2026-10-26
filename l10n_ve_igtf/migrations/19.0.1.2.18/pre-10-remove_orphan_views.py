"""Removes the views that l10n_ve_igtf declared in 17 and no longer declares in 19.

What: deletes these views together with the views that inherit from them, via
SQL with util.remove_views. Inheriting views that belong to a module are
deleted; the ones a user created are deactivated and listed in the migration
report.

Why: a view the module stopped declaring is not rewritten by anyone, so it
stays in the database exactly as it came from 17. If its xpath anchors to
something that no longer exists in 19, as soon as a sibling view loads Odoo
revalidates the tree of its model, cannot find the anchor, and the ParseError
aborts the whole upgrade. Odoo's own cleanup, the one for records whose xmlid
disappeared, runs at the very end of the -u: too late.

If it does not run: the -u all dies while loading this module with "Element
'<xpath ...>' cannot be located in parent view". That is how the Odoo.sh flow
simulation on Proalca died without the manual cleanup previously done by
`migration-verify vistas --borrar`.

Why a pre- script of this same module is enough: during an update, Odoo only
applies the views of the modules already loaded and of the one being loaded
(ir.ui.view._filter_loaded_views). This module's views do not count until it
loads, and this script runs right before that.

Why SQL and not the ORM: in a pre- script the model is not fully set up yet,
and an unlink() on ir.ui.view triggers the validation of the tree against an
incomplete model.

Where the list comes from: the code, not a database. These are the views that
the 17 branches (17.0 and l10nve_17.0) declare and 19 no longer does. It works
for any client coming from 17; the ones missing from its database are ignored.

How to revert: not needed. If a view were listed here by mistake, loading the
module creates it again from its data file.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

from odoo.upgrade import util

MODULE = "l10n_ve_igtf"

ORPHAN_VIEWS = [
    "binaural_igtf_res_company",
    "document_tax_totals",
]


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return

    util.remove_views(cr, *(f"{MODULE}.{name}" for name in ORPHAN_VIEWS))
