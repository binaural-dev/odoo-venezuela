from odoo import api, fields, models


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    foreign_amount = fields.Float()

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._complete_amount_from_foreign(vals) for vals in vals_list])

    @api.model
    def _complete_amount_from_foreign(self, vals):
        """Fill `amount` when only the amount in the foreign currency is given.

        In the core `amount` (journal currency) drives and `amount_currency` is only
        computed from it, never the other way around. A line created with a foreign amount
        and `amount` at 0 produces an entry of 0 in the company currency on both of its
        lines, and reconciling a payment against it sends the whole value of the payment to
        the exchange difference account (ticket #16410). Here `amount` is the foreign amount
        converted at the rate of the statement date. An explicit `amount` is respected.
        """
        if vals.get("amount") or not vals.get("foreign_currency_id") or not vals.get("amount_currency"):
            return vals
        journal_id = vals.get("journal_id") or self.default_get(["journal_id"]).get("journal_id")
        journal = (
            self.env["account.journal"].browse(journal_id)
            if journal_id
            else self.env["account.bank.statement"].browse(vals.get("statement_id")).journal_id
        )
        if not journal:
            return vals
        company = journal.company_id
        journal_currency = journal.currency_id or company.currency_id
        foreign_currency = self.env["res.currency"].browse(vals["foreign_currency_id"])
        if foreign_currency == journal_currency:
            return vals
        date = vals.get("date") or fields.Date.context_today(self)
        return {
            **vals,
            "amount": foreign_currency._convert(
                vals["amount_currency"], journal_currency, company, date
            ),
        }

    def _foreign_conversion_currencies(self):
        """Return (journal currency, foreign currency) if the line converts between them."""
        self.ensure_one()
        if not self.foreign_currency_id or not self.currency_id or self.foreign_currency_id == self.currency_id:
            return None
        return self.currency_id, self.foreign_currency_id

    @api.onchange("amount_currency", "foreign_currency_id")
    def _onchange_amount_currency_sync_amount(self):
        """The foreign amount drives: `amount` follows the rate of the date (ticket #16410).

        It is not triggered by the date or the journal: there the amount in the journal
        currency, which is what the bank moved, wins (see the onchange of `amount`).
        """
        for line in self:
            currencies = line._foreign_conversion_currencies()
            if currencies and line.amount_currency:
                journal_currency, foreign_currency = currencies
                date = line.date or fields.Date.context_today(line)
                # Already coherent (the other onchange has just rounded the foreign amount):
                # do not overwrite `amount`
                expected = journal_currency._convert(line.amount, foreign_currency, line.company_id, date)
                if foreign_currency.compare_amounts(expected, line.amount_currency):
                    line.amount = foreign_currency._convert(
                        line.amount_currency, journal_currency, line.company_id, date
                    )

    @api.onchange("amount", "date", "journal_id")
    def _onchange_amount_sync_amount_currency(self):
        """The journal-currency amount drives: `amount_currency` follows the rate of the date.

        Changing the date or the journal keeps `amount`, which is what the bank moved and
        what the statement balance is built from, and recomputes the foreign amount
        (ticket #16410).
        """
        for line in self:
            currencies = line._foreign_conversion_currencies()
            if currencies and line.amount:
                journal_currency, foreign_currency = currencies
                date = line.date or fields.Date.context_today(line)
                # Already coherent (the other onchange has just rounded `amount`): do not
                # overwrite the foreign amount
                expected = foreign_currency._convert(line.amount_currency, journal_currency, line.company_id, date)
                if not line.amount_currency or journal_currency.compare_amounts(expected, line.amount):
                    line.amount_currency = journal_currency._convert(
                        line.amount, foreign_currency, line.company_id, date
                    )

    def edit_reconcile_line(self, move_line_id, record_data):
        """Keep `balance` and `amount_currency` coherent with the rate of the entry date.

        The "Edit line" dialog of the reconciliation widget lets the user edit the balance
        (company currency) and the amount in another currency at the same time, and the
        core stores both as they come: e.g. USD 1,700 with 1,700,000 Bs (implicit rate
        1000) when the rate of the date was 924.3534. Here the last edited field wins, as
        the onchange of the core does in a manual entry (ticket #16410).
        """
        record_data = self._sync_edited_line_amounts(move_line_id, record_data)
        return super().edit_reconcile_line(move_line_id, record_data)

    def _sync_edited_line_amounts(self, move_line_id, record_data):
        """Complete `record_data` so balance and amount in currency follow the rate of the date.

        - The amount in currency changes: the balance is amount / rate.
        - Only the balance or the currency changes: the amount in currency is balance * rate.
        - Nothing is done if the currency is the company one or the line is already
          reconciled (the partial amount to reconcile follows the rate of the document,
          not the one of the date).
        """
        self.ensure_one()
        line = self.env["account.move.line"].browse(move_line_id)
        company_currency = self.company_id.currency_id
        currency = self.env["res.currency"].browse(
            record_data.get("currency_id", line.currency_id.id)
        )
        if (
            not {"amount_currency", "balance", "currency_id"} & set(record_data)
            or currency == company_currency
            or line.reconciled_lines_ids
        ):
            return record_data
        rate = self.env["res.currency"]._get_conversion_rate(
            company_currency, currency, self.company_id, self.date
        )
        data = dict(record_data)
        if "amount_currency" in data:
            data["balance"] = company_currency.round(data["amount_currency"] / rate)
        else:
            balance = data.get("balance", line.balance)
            data["amount_currency"] = currency.round(balance * rate)
        return data

    def _prepare_move_line_default_vals(self, counterpart_account_id=None):
        liquidity_line_vals, counterpart_line_vals = super()._prepare_move_line_default_vals(
            counterpart_account_id=counterpart_account_id
        )
        if not self.env.company.foreign_currency_id.is_zero(self.foreign_amount):
            liquidity_line_vals.update(
                {
                    "foreign_debit": self.foreign_amount > 0 and self.foreign_amount or 0.0,
                    "foreign_credit": self.foreign_amount < 0 and -self.foreign_amount or 0.0,
                    "not_foreign_recalculate": True,
                }
            )
            counterpart_line_vals.update(
                {
                    "foreign_debit": -self.foreign_amount if self.foreign_amount < 0.0 else 0.0,
                    "foreign_credit": self.foreign_amount if self.foreign_amount > 0.0 else 0.0,
                    "not_foreign_recalculate": True,
                }
            )

        return [liquidity_line_vals, counterpart_line_vals]
