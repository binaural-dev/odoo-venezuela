from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    acl = env.ref("sale.access_sale_order_manager", raise_if_not_found=False)
    if acl:
        acl.perm_unlink = True
