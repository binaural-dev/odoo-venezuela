# -*- coding: utf-8 -*-
# Copyright (C) Softhealer Technologies.

from odoo import models, fields


class Users(models.Model):
    _inherit = 'res.users'

    sh_direct_redirect = fields.Boolean('Redirect to Kiosk ?')
