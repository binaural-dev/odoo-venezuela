# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields


class AfterPages(models.Model):
    _name = 'default.after.pages'
    _description = 'Stores the values of the Default After Pages'

    name = fields.Char("Title", required=True)
    after_datas = fields.Binary("Page Details (PDF only)")
