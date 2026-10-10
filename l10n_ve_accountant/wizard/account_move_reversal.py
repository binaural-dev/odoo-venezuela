from odoo import _, api, fields, models
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
        if len(moves) == 1 and moves.is_invoice(include_receipts=True) and "date" in fields_list:
            res["date"] = moves.invoice_date_display or moves.date
        return res

    def _prepare_default_reversal(self, move):
        values = super()._prepare_default_reversal(move)
        if move.is_invoice(include_receipts=True):
            # The credit note is the same transaction as its origin: document
            # date (`invoice_date_display`) and rate date (`invoice_date`) are
            # carried over, never taken from the wizard.
            document_date = move.invoice_date_display or move.date
            values.update({
                "date": document_date,
                "invoice_date_display": document_date,
                "invoice_date": move.invoice_date or document_date,
                "invoice_date_due": document_date,
                "auto_post": "at_date" if document_date > fields.Date.context_today(self) else "no",
            })
        return values

    def reverse_moves(self, is_modify=False):
        self.ensure_one()
        self._l10n_ve_check_single_invoice(self.move_ids)
        return super().reverse_moves(is_modify=is_modify)
