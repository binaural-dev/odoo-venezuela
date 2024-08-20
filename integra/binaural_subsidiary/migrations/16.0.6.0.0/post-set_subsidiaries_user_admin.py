import logging
from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})

    base_admin_user = env.ref('base.user_admin')
    subsidiary_ids = env["account.analytic.account"].search([("is_subsidiary", "=", True)])

    if not subsidiary_ids:
        return True


    base_admin_user.write({
        'subsidiary_ids': [[6, False, subsidiary_ids.ids]]
    })
