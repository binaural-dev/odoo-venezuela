# Copyright (C) Softhealer Technologies.
# Part of Softhealer Technologies.

from odoo import models, fields, api


class PosSessionInherit(models.Model):
    _inherit = 'pos.session'

    sh_analytic_account = fields.Many2one(
        'account.analytic.account', string='Analytic Account', readonly=False)


    def _validate_session(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        res = super(PosSessionInherit, self)._validate_session(balancing_account, amount_to_balance, bank_payment_method_diffs)
        all_related_moves = self._get_related_account_moves()
        for move in all_related_moves:
            for line in move.line_ids:
                if self.sh_analytic_account:
                    line.write({'analytic_distribution': {self.sh_analytic_account.id: 100}})
        return res
