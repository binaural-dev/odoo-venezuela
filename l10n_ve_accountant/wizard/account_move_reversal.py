from odoo import _, api, models
from odoo.exceptions import UserError


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    @api.model
    def _l10n_ve_check_single_invoice(self, moves):
        """A credit note is issued against ONE invoice only."""
        if len(moves) > 1 and any(m.is_invoice(include_receipts=True) for m in moves):
            raise UserError(_(
                "A credit note can only be issued against a single invoice. "
                "Please select one invoice at a time."
            ))

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        moves = self.env["account.move"].browse(
            self.env.context["active_ids"]
        ) if self.env.context.get("active_model") == "account.move" else self.env["account.move"]
        self._l10n_ve_check_single_invoice(moves)
        return res

    def _prepare_default_reversal(self, move):
        values = super()._prepare_default_reversal(move)
        if move.is_invoice(include_receipts=True):
            # The credit note is the same transaction as its origin: the
            # rate date (`invoice_date`) is always the origin's, while the
            # document date (`invoice_date_display`) is the wizard's date,
            # validated in `reverse_moves` to lie between the origin's date
            # and today.
            values.update({
                "invoice_date_display": self.date,
                "invoice_date": move.invoice_date or move.invoice_date_display or move.date,
            })
        return values

    def reverse_moves(self, is_modify=False):
        self.ensure_one()
        self._l10n_ve_check_single_invoice(self.move_ids)
        self.move_ids._l10n_ve_check_note_date(self.date)
        return super().reverse_moves(is_modify=is_modify)
