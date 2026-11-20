from odoo import fields, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    pos_company_amount = fields.Monetary(
        currency_field="company_currency_id",
        readonly=True,
        copy=False,
        help="Exact company currency amount of a point of sale cash line booked "
        "in a journal in another currency: the cash paid in dollars that goes to "
        "the dollar cash journal of its currency, or the bolivares handed over in "
        "a register in dollars. When empty, the entry converts the amount at the "
        "date of the line.",
    )

    def _prepare_move_line_default_vals(self, counterpart_account_id=None):
        """Entry of the statement line with the exact company currency amount.

        ``l10n_ve_accountant`` accepts no line in a currency other than the one
        of the journal, so a cash line in a journal in dollars cannot carry its
        bolivares as ``foreign_currency_id``: both lines stay in the currency of
        the journal and ``pos_company_amount`` goes to their company columns,
        without touching ``amount_currency``. Applied here, like
        ``foreign_amount`` in ``l10n_ve_accountant``, so the synchronisation of
        the entry (``_synchronize_to_moves``) respects it too.
        """
        liquidity_line_vals, counterpart_line_vals = super()._prepare_move_line_default_vals(
            counterpart_account_id=counterpart_account_id
        )
        company_currency = self.journal_id.company_id.sudo().currency_id
        journal_currency = self.journal_id.currency_id
        if not journal_currency or journal_currency == company_currency:
            return [liquidity_line_vals, counterpart_line_vals]
        company_amount = self.pos_company_amount
        if company_currency.is_zero(company_amount):
            return [liquidity_line_vals, counterpart_line_vals]
        liquidity_line_vals.update({
            "debit": company_amount if company_amount > 0 else 0.0,
            "credit": -company_amount if company_amount < 0 else 0.0,
        })
        counterpart_line_vals.update({
            "debit": -company_amount if company_amount < 0 else 0.0,
            "credit": company_amount if company_amount > 0 else 0.0,
        })
        return [liquidity_line_vals, counterpart_line_vals]

    def write(self, vals):
        """A change of amount, currency or journal invalidates
        ``pos_company_amount``: the entry goes back to the conversion of the
        core. The synchronisation with the entry writes the same ``amount``
        back and leaves it alone."""
        if "pos_company_amount" not in vals and any(
            self._invalidates_company_amount(line, vals) for line in self
        ):
            vals = dict(vals, pos_company_amount=0.0)
        return super().write(vals)

    @staticmethod
    def _invalidates_company_amount(line, vals):
        if not line.pos_company_amount:
            return False
        if "amount" in vals and line.currency_id.compare_amounts(vals["amount"], line.amount):
            return True
        if "journal_id" in vals and vals["journal_id"] != line.journal_id.id:
            return True
        return bool(
            (
                "foreign_currency_id" in vals
                and (vals["foreign_currency_id"] or False) != (line.foreign_currency_id.id or False)
            )
            or ("amount_currency" in vals and vals["amount_currency"] != line.amount_currency)
        )
