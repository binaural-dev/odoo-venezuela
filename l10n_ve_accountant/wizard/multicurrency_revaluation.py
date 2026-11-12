from odoo import api, models


class AccountMulticurrencyRevaluationWizard(models.TransientModel):
    _inherit = "account.multicurrency.revaluation.wizard"

    @api.model
    def _get_move_vals(self):
        """EXTENDS core: the unrealized currency adjustment entry only moves the
        company currency (VEF).

        The native wizard adjusts only `debit`/`credit` and creates the lines
        with `amount_currency = 0`: in the alternate currency there is no
        difference at all (100 USD are still 100 USD, only their VEF value
        changes). Without this flag, `_get_foreign_value` discards the
        "line already in alternate currency" branch because `amount_currency`
        is zero and, since the entry is not an invoice, falls back to
        `_get_non_invoice_foreign_value`, which converts the VEF adjustment to
        USD at the date rate and leaves alternate amounts that do not exist
        (receivable, payable and exchange gain/loss in USD).

        `not_foreign_recalculate` makes `_skip_foreign_compute` and the
        entry-level computation skip these lines, and `foreign_debit` /
        `foreign_credit` are set to 0. The reversal created by `create_entries`
        copies the lines (and this flag), so it also stays at 0 in the
        alternate currency.
        """
        move_vals = super()._get_move_vals()
        for command in move_vals.get("line_ids", []):
            command[2].update(
                {
                    "not_foreign_recalculate": True,
                    "foreign_debit": 0.0,
                    "foreign_credit": 0.0,
                }
            )
        return move_vals
