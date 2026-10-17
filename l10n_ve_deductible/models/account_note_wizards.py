from odoo import models


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    def _modify_default_reverse_values(self, origin_move):
        """"Reverse and modify" creates a replacement of the bill: it keeps the
        deductible so only the corrections have to be made."""
        data = super()._modify_default_reverse_values(origin_move)
        data.update(origin_move._get_deductible_copy_values())
        return data


class AccountDebitNote(models.TransientModel):
    _inherit = "account.debit.note"

    def _prepare_default_values(self, move):
        """A debit note keeps the deductible of its bill when the lines are
        copied. Without lines there is nothing to deduct from (the amount must
        be below the total of the lines), so it starts as a plain note."""
        default_values = super()._prepare_default_values(move)
        if self.copy_lines:
            default_values.update(move._get_deductible_copy_values())
        return default_values
