from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    # La regla vive en un bloque noupdate: sin esta migracion las bases existentes
    # conservarian el dominio anterior (company_id in company_ids).
    env = api.Environment(cr, SUPERUSER_ID, {})
    rule = env.ref("l10n_ve_stock.product_category_multi_company_rule", raise_if_not_found=False)
    if rule:
        rule.domain_force = "['|', ('company_id', '=', False), ('company_id', 'parent_of', company_ids)]"
