from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _create_payment_move(self, line_vals, payment):
        move = super()._create_payment_move(line_vals, payment)
        move.button_draft()
        move.account_analytic_id = payment.account_analytic_id.id
        move.action_post()
        return move
