"""Give group_foreign_currency_view_accountant to the internal users coming from v17.

What: adds every internal user (share = False), active and archived, to the group.

Why: the group is new in v19 (6933e4079) and protects the invoice "Foreign currency" tab, with the
    totals in the alternate currency (views/account_move.xml). In v17 that tab had no group: anyone
    opening an invoice saw it. The group is not seeded on any user, not even base.user_admin, so
    after the -u all nobody sees it. That is how proalca19_db ended up in session 13, with 0 users
    in the group.

    It is given to all internal users and not only to accounting so that the migration does not
    change what each user saw in v17. Who should have it from then on is the client's decision,
    made from Settings → Users.

If it does not run: the tab with the $ totals disappears for everyone on every migrated invoice.

How to revert: remove the users from the group in Settings. No other data is touched.

Task: https://binaural.odoo.com/odoo/action-1963/4199/action-345/82849
"""

import logging

from odoo.upgrade import util

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version or not version.startswith("17."):
        return

    env = util.env(cr)
    group = env.ref("l10n_ve_accountant.group_foreign_currency_view_accountant", raise_if_not_found=False)
    if not group:
        return
    users = env["res.users"].with_context(active_test=False).search([("share", "=", False)]) - group.user_ids
    if users:
        group.write({"user_ids": [(4, user.id) for user in users]})
    _logger.info("%s internal users added to %s", len(users), group.name)
