# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields

class BeforePages(models.Model):
    _name = 'default.before.pages'
    _description = 'Stores the values of the Default Before Pages'

    name = fields.Char("Title",required=True)
    before_datas = fields.Binary("Page Details (PDF only)", required=True)
