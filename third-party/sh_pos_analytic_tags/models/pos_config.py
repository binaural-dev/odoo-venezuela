# Copyright (C) Softhealer Technologies.
# Part of Softhealer Technologies.

from odoo import models, fields, api

class Posconfiginherit(models.Model):
    _inherit = 'pos.config'

    sh_analytic_account = fields.Many2one(
        'account.analytic.account', string="Analytic Account")

    def _action_to_open_ui(self):
        res = super()._action_to_open_ui()
        self.current_session_id.write(
            {'sh_analytic_account': self.sh_analytic_account})
        return res