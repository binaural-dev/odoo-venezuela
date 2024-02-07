# Copyright (C) Softhealer Technologies.
# Part of Softhealer Technologies.

from odoo import models, fields, api

class PosPaymentInherit(models.Model):
    _inherit = 'pos.payment'

    sh_analytic_account = fields.Many2one(
        'account.analytic.account', string='Analytic Account')





