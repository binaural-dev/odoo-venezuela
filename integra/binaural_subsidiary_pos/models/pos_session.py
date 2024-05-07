from odoo import fields, models


class PosSession(models.Model):
    _inherit = "pos.session"

    sh_analytic_account = fields.Many2one(string="Subsidiary")

    def _validate_session(
        self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None
    ):
        res = super()._validate_session(
            balancing_account, amount_to_balance, bank_payment_method_diffs
        )
        all_related_moves = self._get_related_account_moves()
        for move in all_related_moves:
            if self.sh_analytic_account:
                move.write({"account_analytic_id": self.sh_analytic_account.id})
        return res
