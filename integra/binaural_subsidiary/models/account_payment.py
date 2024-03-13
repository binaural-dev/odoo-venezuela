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
        related="company_id.subsidiary",
        store=True,
        string="Company Subsidiary",
    )

    def _synchronize_to_moves(self, changed_fields):
        """
        Override the original method to change the analytic account (subidiary) of the move using
        the one from the payment.
        """
        res = super()._synchronize_to_moves(changed_fields)
        for payment in self.with_context(skip_account_move_synchronization=True):
            if not payment.account_analytic_id:
                continue
            payment.move_id.write({"account_analytic_id": payment.account_analytic_id.id})
        return res

    def _synchronize_from_moves(self, changed_fields):
        """
        Override the original method to change the analytic account (subidiary) of the payment using
        the one from the move.
        """
        res = super()._synchronize_to_moves(changed_fields)
        for payment in self.with_context(skip_account_move_synchronization=True):
            move = payment.move_id
            if move.statement_line_id:
                continue

            if not move.account_analytic_id:
                continue
            payment.write({"account_analytic_id": move.account_analytic_id.id})
        return res

    def correccion_subsidiary_account_payment(self):
        for payment in self:
            move = payment.move_id
            if move.invoice_line_ids:
                subsidiary_id = move.invoice_line_ids[0].analytic_distribution
                if subsidiary_id:
                    subsidiary_id = subsidiary_id.keys()
                    for subsidiary in subsidiary_id:
                        subsidiary_id = subsidiary
                    payment.account_analytic_id = self.env["account.analytic.account"].search(
                        [("id", "=", subsidiary_id)]
                    )
