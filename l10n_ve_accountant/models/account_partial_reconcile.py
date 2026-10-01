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
        for payment methods with their own `payment_account_id`.

        Also a safety net: ensures our alt-diff entries (combined +
        standalone) get reversed on unlink even when a third-party flow
        breaks the reconciliation without going through the ordinary path
        (see `l10n-ve-foreign-currency-exchange-difference` openspec).
        No-op if core's own `exchange_move_id` reversal already did the
        job. Restored here after the merge with the payment_state fix
        above silently dropped it (both rewrote this same method from
        diverging bases)."""
        affected_moves = (self.debit_move_id | self.credit_move_id).move_id.filtered(
            lambda m: m.is_invoice(include_receipts=True)
        )
        to_verify = self.exchange_move_id.filtered(
            lambda m: m.l10n_ve_exchange_foreign_diff_entry
        )
        res = super().unlink()
        affected_moves = affected_moves.exists()
        if affected_moves:
            self.env.add_to_compute(
                self.env['account.move']._fields['payment_state'], affected_moves
            )
        for move in to_verify:
            if move.exists() and move.state == 'posted' and not move.reversal_move_ids:
                move._reverse_moves([{
                    'date': move._get_accounting_date(move.date, move._affect_tax_report()),
                    'ref': _('Reversal of: %s', move.name),
                }], cancel=True)
        return res
