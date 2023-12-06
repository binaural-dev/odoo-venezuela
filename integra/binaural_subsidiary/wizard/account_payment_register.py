from odoo import api, fields, models, _


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    account_analytic_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        domain=[("is_subsidiary", "=", True)],
    )

    def _init_payments(self, to_process, edit_mode=False):
        """
        Override the original method to add the analytic account to the payments.
        """
        payments = super()._init_payments(to_process, edit_mode)
        for payment in payments:
            payment.account_analytic_id = self.account_analytic_id.id
        return payments
