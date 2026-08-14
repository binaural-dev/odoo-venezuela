from odoo import api, models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    @api.depends(
        "can_edit_wizard",
        "source_amount",
        "source_amount_currency",
        "source_currency_id",
        "company_id",
        "currency_id",
        "payment_date",
    )
    def _compute_amount(self):
        super()._compute_amount()
        for wizard in self:
            if getattr(wizard, "is_igtf", False):
                # l10n_ve_igtf owns `amount` entirely for IGTF payments (and
                # has its own pre-existing, unrelated issues in that path) -
                # do not touch it here.
                continue
            if wizard.early_payment_discount_mode:
                # Early payment discount changes the meaning of `amount`;
                # out of scope for this feature.
                continue
            invoice = wizard._get_split_rate_invoice()
            if not invoice or not invoice.foreign_rate:
                continue
            blended_amount = wizard._compute_split_rate_amount(invoice)
            if blended_amount is not None:
                wizard.amount = blended_amount
                wizard._apply_split_rate_writeoff()

    def _apply_split_rate_writeoff(self):
        """The blended `amount` deliberately pays less than a plain,
        single-rate conversion of the invoice's residual would (that's the
        whole point: the IVA portion is frozen at the invoice's own rate,
        not revalued). Left alone, Odoo's own reconciliation converts the
        payment back to the invoice's currency using ONE rate and leaves a
        residual open instead of closing the invoice - so this also
        configures the wizard's own native "mark as fully paid" mechanism,
        routed through one of the company's exchange gain/loss accounts.
        That makes core treat the gap as a natural currency exchange
        difference (the exact same mechanism it already uses for any other
        cross-rate payment - see account.payment.register's own
        `writeoff_is_exchange_account`/`force_balance` handling) instead of
        leaving a confusing open balance behind.
        """
        self.ensure_one()
        exchange_account = (
            self.company_id.expense_currency_exchange_account_id
            or self.company_id.income_currency_exchange_account_id
        )
        if not exchange_account or self.currency_id.is_zero(self.payment_difference):
            return
        self.payment_difference_handling = "reconcile"
        self.writeoff_account_id = exchange_account.id

    def _get_split_rate_invoice(self):
        """The single invoice/credit note this wizard is paying, or an
        empty recordset if it covers zero or more than one move - multi-
        invoice batches are out of scope for this feature.
        """
        self.ensure_one()
        moves = self.line_ids._origin.mapped("move_id")
        if len(moves) != 1 or not moves.is_invoice(include_receipts=True):
            return self.env["account.move"]
        return moves

    def _compute_split_rate_amount(self, invoice):
        """Blend the wizard's suggested amount: the tax (IVA) portion still
        pending is priced at the invoice's own frozen `foreign_rate`, and
        the untaxed (BI) portion still pending is priced at the wizard's
        current rate (today's/payment_date's rate, following `currency_id`).

        Both portions are taken proportionally to the invoice's current
        `amount_residual` (not the full original amount_tax/amount_untaxed),
        so this stays correct after a prior partial payment.
        """
        self.ensure_one()
        if invoice.currency_id.is_zero(invoice.amount_total):
            return None

        proportion = invoice.amount_residual / invoice.amount_total
        iva_residual = abs(invoice.amount_tax * proportion)
        bi_residual = abs(invoice.amount_untaxed * proportion)

        bi_amount = invoice.currency_id._convert(
            bi_residual, self.currency_id, self.company_id, self.payment_date,
        )
        iva_amount = self._convert_at_frozen_rate(
            iva_residual, invoice.currency_id, invoice.foreign_rate,
        )
        return bi_amount + iva_amount

    def _convert_at_frozen_rate(self, amount, from_currency, frozen_rate):
        """Convert `amount` (in from_currency) into self.currency_id using
        the invoice's own FROZEN foreign_rate (VEF per unit of the
        company's foreign currency, e.g. USD - see l10n_ve_accountant's
        account.move.foreign_rate) instead of a fresh res.currency.rate
        lookup by date. A date-based lookup can pick up a rate that
        doesn't match the one actually stored on the invoice and produce a
        wildly wrong result - same reasoning already documented in
        maxcam_exchange_rate_differences._compute_foreign_exchange_difference.
        """
        self.ensure_one()
        company_currency = self.company_currency_id
        foreign_currency = self.company_id.foreign_currency_id
        if from_currency == company_currency and self.currency_id == foreign_currency:
            return amount / frozen_rate if frozen_rate else 0.0
        if from_currency == foreign_currency and self.currency_id == company_currency:
            return amount * frozen_rate
        if from_currency == self.currency_id:
            return amount
        # Invoice currency is neither the company currency nor the
        # company's declared foreign currency (a genuine 3rd-currency
        # invoice) - the frozen-rate direction isn't well-defined for this
        # combination in this codebase's bimonetary conventions. Fall back
        # to a live convert rather than silently dropping the amount.
        return from_currency._convert(
            amount, self.currency_id, self.company_id, self.payment_date,
        )
