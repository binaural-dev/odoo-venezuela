"""Remove the views l10n_ve_invoice_digital declared in v17 and v19 no longer does.

What: removes these views, together with the ones inheriting from them, with util.remove_views.
    Inheriting views that belong to a module are removed; the ones a user created are disabled.

Why: a view the module stopped declaring stays in the database as it came from v17 until Odoo's own
    cleanup at the end of the whole -u, which is too late. view_ir_sequence_form_tfhka inherits the
    base sequence form and shows prefix_locked, which v19 removed: the first module loaded after this
    one that touches the sequence form would abort the upgrade. The other two are v17 list views
    (<tree>, renamed in v19).

    The list comes from the code, not from a database: the views 17.0 declares and v19 does not.

If it does not run: the -u all can die with "Field prefix_locked does not exist in model ir.sequence".

How to revert: not needed. If a view were here by mistake, loading the module creates it again from
    its data file.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

from odoo.upgrade import util

MODULE = "l10n_ve_invoice_digital"

ORPHAN_VIEWS = [
    "view_ir_sequence_form_tfhka",
    "view_payment_method_tfhka_tree",
    "view_tfhka_api_log_tree",
]


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return
    util.remove_views(cr, *(f"{MODULE}.{name}" for name in ORPHAN_VIEWS))
