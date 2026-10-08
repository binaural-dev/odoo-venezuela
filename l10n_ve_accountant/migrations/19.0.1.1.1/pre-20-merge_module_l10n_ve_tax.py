"""Merges the l10n_ve_tax module, which does not exist in 19, into l10n_ve_accountant.

What: deletes the l10n_ve_tax views and moves the rest of what the module owns (ir.model,
    ir.model.fields, selections) to l10n_ve_accountant with util.merge_module, which also deletes
    the module record and its dependencies. When the update finishes, Odoo's own cleanup removes
    whatever l10n_ve_accountant does not declare.

Why: the l10n_ve_tax data is already merged by 19.0.1.0.14 (it backs up, renames and drops
    columns), but the module itself stayed in the database with no code. After a -u all:

    - ir_module_module leaves it 'to upgrade' forever: "Some modules have inconsistent
      states, some dependencies may be missing: ['l10n_ve_tax']", and migration-verify modulos
      flags the graph as unhealthy.
    - Its 3 views stay active, and view_account_move_form_binaural_tax uses
      international_purchase_exempt_product, which in 19 is named
      international_purchase_exent_product: "invalid custom view(s) for model account.move ...
      Field "international_purchase_exempt_product" does not exist in model "account.move.line"".

    Until now the manual preparation marked it 'uninstalled' via SQL before the -u all, but that
    still left its views and its xmlids dangling. On Odoo.sh that step does not exist.

Why the views are deleted before the merge: if they moved to l10n_ve_accountant, they would be
    applied when loading it (ir.ui.view._filter_loaded_views) and the account.move one would crash
    its loading.

Why it is marked 'uninstalled' before the merge: if the merged module is installed,
    merge_module calls force_install_module on the target, and outside the base scripts that
    triggers module auto-discovery or aborts with MigrationError. l10n_ve_accountant is already
    installed, so it is not needed.

What is lost: nothing with data. The 10 fields that only l10n_ve_tax declared no longer have a
    column: the 19.0.1.0.14 post-migrate drops them, except international_purchase_exempt_product,
    which its pre-migrate renames to the v19 name with its data. In Proalca they were empty in v17.
    The 6 ir.model are for models that l10n_ve_accountant also extends: merge_module only deletes
    the duplicate xmlid.

If it does not run: the migration finishes, but with an unhealthy graph and a broken view on the
    invoice form.

How to revert: there is nothing to revert. The module has no code in 19 and its data was already
    migrated.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

from odoo.upgrade import util

ABSORBED = "l10n_ve_tax"
INTO = "l10n_ve_accountant"


def migrate(cr, version):
    if not version or not util.module_installed(cr, ABSORBED):
        return

    cr.execute(
        """
        SELECT module || '.' || name
          FROM ir_model_data
         WHERE module = %s
           AND model = 'ir.ui.view'
        """,
        [ABSORBED],
    )
    xml_ids = [xml_id for (xml_id,) in cr.fetchall()]
    if xml_ids:
        util.remove_views(cr, *xml_ids)

    cr.execute("UPDATE ir_module_module SET state = 'uninstalled' WHERE name = %s", [ABSORBED])
    util.merge_module(cr, ABSORBED, INTO)
