from odoo import api, fields, models, _


class AccountMove(models.Model):
    _inherit = "account.move"

    def _reconcile_move_with_payment_difference(self, move_id, move_to_reconcile):
        move_to_reconcile.account_analytic_id = move_id.account_analytic_id.id
        return super()._reconcile_move_with_payment_difference(move_id, move_to_reconcile)
