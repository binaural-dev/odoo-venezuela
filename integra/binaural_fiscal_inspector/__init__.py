from odoo import SUPERUSER_ID, api

from . import models


def create_res_users_fiscal(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    binaural_subsidiary_module = env['ir.module.module'].search([('name', '=', 'binaural_subsidiary'), ('state', '=', 'installed')])

    user_data = {
        'name': 'Inspector Fiscal',
        'login': 'inspector@fiscal',
        'sel_groups_1_10_11': 1,
        'company_id': env.ref('base.main_company').id,
        'company_ids': [env.ref('base.main_company').id],
        'groups_id': [(4, env.ref('binaural_fiscal_inspector.group_fiscal_inspectorate').id)],
    }

    if binaural_subsidiary_module:
        if env.ref('base.main_company').subsidiary:

            subsidiary = env['account.analytic.account'].search([('company_id', '=', env.ref('base.main_company').id), ('is_subsidiary', '=', True)], limit=1)

            if not subsidiary:
                account_analytic_plan = env['account.analytic.plan'].create({
                    'name': 'Main Subsidiary Plan',
                    'default_applicability': 'unavailable'

                })
                account_analytic_account = env['account.analytic.account'].create({
                    'name': 'Main Subsidiary',
                    'plan_id': account_analytic_plan.id,
                    'is_subsidiary': True

                })

                subsidiary = account_analytic_account


            user_data['subsidiary_id'] = subsidiary.id
            user_data['subsidiary_ids'] = [subsidiary.id]

    env['res.users'].create(user_data)