from odoo import fields, models, _


class AccountPayment(models.Model):
    _inherit = "account.payment"

    account_analytic_id = fields.Many2one(
        "account.analytic.account",
        string="Subsidiary",
        domain=lambda self: (
            f"[('is_subsidiary', '=', True),('id', 'in', {self.env.user.subsidiary_ids.ids})]"
        ),
        tracking=True,
    )

    company_subsidiary = fields.Boolean(
        related='company_id.subsidiary', store=True,
    )
    
    def _synchronize_to_moves(self, changed_fields):
        """
        Override the original method to change the analytic account (subidiary) of the move using
        the one from the payment.
        """
        res = super()._synchronize_to_moves(changed_fields)
        for payment in self.with_context(skip_account_move_synchronization=True):
            payment.move_id.write({"account_analytic_id": payment.account_analytic_id.id})
        return res

    def correccion_subsidiary_account_payment(self):
        for payment in self:
            payment.account_analytic_id = payment.move_id.account_analytic_id