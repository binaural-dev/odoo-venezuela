from odoo import fields, models, _


class AccountPartialReconcile(models.Model):
    _inherit = "account.partial.reconcile"

    debit_move_foreign_inverse_rate = fields.Float(
        related="debit_move_id.foreign_inverse_rate",
        store=True,
        index=True,
    )
    credit_move_foreign_inverse_rate = fields.Float(
        related="credit_move_id.foreign_inverse_rate",
        store=True,
        index=True,
    )

    def unlink(self):
        """Force-recomputes `payment_state` (lazily) on invoices/bills this
        partial touched -- core's own recompute can otherwise stay stale
        for payment methods with their own `payment_account_id`."""
        affected_moves = (self.debit_move_id | self.credit_move_id).move_id.filtered(
            lambda m: m.is_invoice(include_receipts=True)
        )
        res = super().unlink()
        affected_moves = affected_moves.exists()
        if affected_moves:
            self.env.add_to_compute(
                self.env['account.move']._fields['payment_state'], affected_moves
            )
        return res
