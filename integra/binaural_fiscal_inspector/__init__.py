from odoo import SUPERUSER_ID, api

from . import models


def create_res_users_fiscal(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    binaural_subsidiary_module = env['ir.module.module'].search([('name', '=', 'binaural_subsidiary'), ('state', '=', 'installed')])

    if binaural_subsidiary_module:
        env['res.users'].create({
            'name': 'Inspector Fiscal',
            'login': 'inspector@fiscal',
            'sel_groups_1_10_11': 1,
            'company_id': env.ref('base.main_company').id,
            'company_ids': [env.ref('base.main_company').id],
            'groups_id': [(4, env.ref('binaural_fiscal_inspector.group_fiscal_inspectorate').id)],
            'subsidiary_id': env.ref('binaural_subsidiary.analytic_main_subsidiary').id,
            'subsidiary_ids': [env.ref('binaural_subsidiary.analytic_main_subsidiary').id]
        })

        return

    env['res.users'].create({
        'name': 'Inspector Fiscal',
        'login': 'inspector@fiscal',
        'sel_groups_1_10_11': 1,
        'company_id': env.ref('base.main_company').id,
        'company_ids': [env.ref('base.main_company').id],
        'groups_id': [(4, env.ref('binaural_fiscal_inspector.group_fiscal_inspectorate').id)],
    })