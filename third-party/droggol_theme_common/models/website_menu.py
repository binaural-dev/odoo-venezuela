# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from odoo import api, fields, models


class WebsiteMenu(models.Model):
    _inherit = 'website.menu'

    dr_menu_label_id = fields.Many2one('dr.website.menu.label', string='Label')
    dr_highlight_menu = fields.Selection([('solid', 'Solid'), ('soft', 'Soft')], string='Highlight Menu')

    @api.model
    def get_tree(self, website_id, menu_id=None):
        result = super().get_tree(website_id, menu_id=menu_id)
        for menu in result['children']:
            menu['fields']['dr_highlight_menu'] = self.browse(menu['fields']['id']).dr_highlight_menu
        return result
