from odoo import models


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    def reverse_moves(self, is_modify=False):
        """The replacement of "Reverse and modify" has no link to its origin, so
        it is flagged as inheriting the deductible whatever the company scope."""
        wizard = self.with_context(deductible_inherit=True) if is_modify else self
        return super(AccountMoveReversal, wizard).reverse_moves(is_modify=is_modify)

    def _modify_default_reverse_values(self, origin_move):
        """The replacement created by "Reverse and modify" keeps the deductible
        of the reversed document, so only the corrections have to be made."""
        data = super()._modify_default_reverse_values(origin_move)
        data.update(origin_move._get_deductible_copy_values())
        return data


class AccountDebitNote(models.TransientModel):
    _inherit = "account.debit.note"

    def _prepare_default_values(self, move):
        """A debit note keeps the deductible of its document when the lines are
        copied. Without lines there is nothing to deduct from (the amount must
        be below the total of the lines), so it starts as a plain note."""
        default_values = super()._prepare_default_values(move)
        if self.copy_lines:
            default_values.update(move._get_deductible_copy_values())
        return default_values
