# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from odoo import api, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    dr_pwa_activated = fields.Boolean(related='website_id.dr_pwa_activated', readonly=False)
    dr_pwa_name = fields.Char(related='website_id.dr_pwa_name', readonly=False)
    dr_pwa_short_name = fields.Char(related='website_id.dr_pwa_short_name', readonly=False)
    dr_pwa_background_color = fields.Char(related='website_id.dr_pwa_background_color', readonly=False)
    dr_pwa_theme_color = fields.Char(related='website_id.dr_pwa_theme_color', readonly=False)
    dr_pwa_icon_192 = fields.Binary(related='website_id.dr_pwa_icon_192', readonly=False)
    dr_pwa_icon_512 = fields.Binary(related='website_id.dr_pwa_icon_512', readonly=False)
    dr_pwa_start_url = fields.Char(related='website_id.dr_pwa_start_url', readonly=False)
    dr_pwa_shortcuts = fields.One2many(related='website_id.dr_pwa_shortcuts', readonly=False)
    dr_pwa_offline_page = fields.Boolean(related='website_id.dr_pwa_offline_page', readonly=False)

    # This has been done in order to fix Odoo's broken behavior for theme customization.
    # If database already have theme installed, it is impossible to have custom module later.
    dr_has_custom_module = fields.Boolean(compute='_compute_dr_has_custom_module')

    @api.depends('website_id')
    def _compute_dr_has_custom_module(self):
        IrModuleModule = self.env['ir.module.module']
        themes = self._get_droggol_theme_list()
        for setting in self:
            setting.dr_has_custom_module = False
            if setting.website_id and setting.website_id.theme_id and setting.website_id.theme_id.name in themes:
                search_term = '%s_%%' % setting.website_id.theme_id.name
                has_custom_apps = IrModuleModule.sudo().search([('name', '=ilike', search_term)])
                setting.dr_has_custom_module = bool(has_custom_apps)

    def dr_open_pwa_shortcuts(self):
        self.website_id._force()
        action = self.env.ref('droggol_theme_common.dr_pwa_shortcuts_action').read()[0]
        action['domain'] = [('website_id', '=', self.website_id.id)]
        action['context'] = {'default_website_id': self.website_id.id}
        return action

    def dr_open_theme_custom_modules(self):
        self.ensure_one()
        themes = self._get_droggol_theme_list()
        if self.website_id and self.website_id.theme_id and self.website_id.theme_id.name in themes:
            search_term = '%s_%%' % self.website_id.theme_id.name
            return {
                'name': _('Theme Customizations'),
                'view_mode': 'kanban,tree,form',
                'res_model': 'ir.module.module',
                'type': 'ir.actions.act_window',
                'domain': [('name', '=ilike', search_term)]
            }
        return True

    def _get_droggol_theme_list(self):
        return ['theme_prime']
