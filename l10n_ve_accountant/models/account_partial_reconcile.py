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
        """Safety net: ensures our alt-diff entries (combined + standalone)
        get reversed on unlink even when a third-party flow breaks the
        reconciliation without going through the ordinary path (see
        `l10n-ve-foreign-currency-exchange-difference` openspec). No-op if
        core's own `exchange_move_id` reversal already did the job.
        """
        to_verify = self.exchange_move_id.filtered(
            lambda m: m.l10n_ve_exchange_foreign_diff_entry
        )
        res = super().unlink()
        for move in to_verify:
            if move.exists() and move.state == 'posted' and not move.reversal_move_ids:
                move._reverse_moves([{
                    'date': move._get_accounting_date(move.date, move._affect_tax_report()),
                    'ref': _('Reversal of: %s', move.name),
                }], cancel=True)
        return res
