# -*- coding: utf-8 -*-
# Copyright (c) 2019-Present Droggol Infotech Private Limited. (<https://www.droggol.com/>)

from odoo import fields, models


class PWAShortcuts(models.Model):
    _name = 'dr.pwa.shortcuts'
    _description = 'PWA Shortcuts'

    website_id = fields.Many2one('website')
    sequence = fields.Integer()
    name = fields.Char(required=True, translate=True, help='The human-readable label for the app shortcut when displayed to the user.')
    short_name = fields.Char('Short Name', translate=True, help='The human-readable label used where space is limited.')
    description = fields.Text(help='The human-readable purpose for the app shortcut.')
    url = fields.Char('URL', required=True, help='The URL opened when a user activates the app shortcut.')
    icon = fields.Binary()
