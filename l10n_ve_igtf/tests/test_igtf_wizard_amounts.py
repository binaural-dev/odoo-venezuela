import logging

from odoo.tests import tagged
from odoo import fields

from odoo.addons.l10n_ve_accountant.tests.test_indexed_payments import TestIndexedPayments

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_igtf_wizard_amounts")
class TestIgtfWizardAmounts(TestIndexedPayments):
    """
    Validates the l10n_ve_igtf overrides of account.payment.register's
    _compute_amount / _onchange_amount / _compute_payment_difference, and the
    _is_same_within_rounding helper used to reconcile amounts computed via
    different currency-conversion paths.

    Reuses TestIndexedPayments' setUp (fresh company, VEF/USD/EUR, rates,
    accounts, journals, partner, product, tax) instead of rebuilding fixtures,
    and enables IGTF manually on the wizard (bypassing the is_igtf compute,
    which depends on partner/journal classification not part of this
    fixture) to isolate the amount-calculation logic under test.
    """

    def setUp(self):
        super().setUp()
        self.company.igtf_percentage = 3.0

    def _create_igtf_wizard(self, invoice, amount=None):
        journal = self._get_foreign_bank_journal(self.currency_usd)
        vals = {
            "journal_id": journal.id,
            "currency_id": self.currency_usd.id,
            "payment_date": self.payment_date,
        }
        if amount is not None:
            vals["amount"] = amount
        wizard = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=invoice.ids, active_id=invoice.id,
        ).create(vals)
        wizard.is_igtf = True
        return wizard

    def test_onchange_amount_does_not_stick_custom_user_amount(self):
        """Re-triggering _onchange_amount with the amount the system itself
        proposed must not mark custom_user_amount, and must not shift
        amount_without_difference -- otherwise the wizard would visibly
        recompute IGTF on an amount that already includes IGTF right before
        the user hits "Pagar"."""
        self._set_rate(self.currency_usd, self.invoice_date, 40.0)
        self._set_rate(self.currency_usd, self.payment_date, 40.0)

        invoice = self._create_foreign_invoice(self.currency_usd, amount=100.0)
        wizard = self._create_igtf_wizard(invoice)

        first_amount_without_difference = wizard.amount_without_difference
        self.assertFalse(wizard.custom_user_amount)

        wizard._onchange_amount()

        self.assertFalse(
            wizard.custom_user_amount,
            "custom_user_amount must stay cleared when the amount matches the system's own proposal.",
        )
        self.assertAlmostEqual(
            wizard.amount_without_difference, first_amount_without_difference, places=2,
            msg="amount_without_difference must not shift on a no-op onchange re-trigger.",
        )

    def test_amount_without_difference_shows_debt_when_underpaying_with_reconcile(self):
        """Paying less than owed, with the difference reconciled (not left
        open) to a loss account, must keep amount_without_difference showing
        the real debt -- not "typed amount minus IGTF"."""
        self._set_rate(self.currency_usd, self.invoice_date, 40.0)
        self._set_rate(self.currency_usd, self.payment_date, 40.0)

        invoice = self._create_foreign_invoice(self.currency_usd, amount=100.0)
        wizard = self._create_igtf_wizard(invoice)
        debt = wizard.amount_without_difference  # the real debt, from the default (non-edited) proposal

        wizard.payment_difference_handling = "reconcile"
        wizard.amount = 50.0  # underpay: triggers custom_user_amount

        self.assertAlmostEqual(
            wizard.amount_without_difference, debt, places=2,
            msg="Underpaying with reconcile must anchor amount_without_difference to the real debt.",
        )

    def test_amount_without_difference_uses_typed_amount_when_left_open(self):
        """Same underpayment, but leaving the difference open (not
        reconciled): amount_without_difference falls back to the typed
        amount minus IGTF, since there's no write-off to anchor to a fixed
        debt figure."""
        self._set_rate(self.currency_usd, self.invoice_date, 40.0)
        self._set_rate(self.currency_usd, self.payment_date, 40.0)

        invoice = self._create_foreign_invoice(self.currency_usd, amount=100.0)
        wizard = self._create_igtf_wizard(invoice)

        wizard.payment_difference_handling = "open"
        wizard.amount = 50.0

        self.assertAlmostEqual(
            wizard.amount_without_difference, wizard.amount - wizard.igtf_amount, places=2,
            msg="Left-open underpayment must use typed amount minus IGTF, not the full debt.",
        )

    def test_payment_difference_is_debt_minus_effective_amount(self):
        """payment_difference is computed as amount_for_difference (the debt)
        minus effective_amount (amount typed minus the IGTF recalculated on
        that same typed amount) -- current behavior, regardless of
        payment_difference_handling."""
        self._set_rate(self.currency_usd, self.invoice_date, 40.0)
        self._set_rate(self.currency_usd, self.payment_date, 40.0)

        invoice = self._create_foreign_invoice(self.currency_usd, amount=100.0)
        wizard = self._create_igtf_wizard(invoice)
        total_amount_values = wizard._get_total_amounts_to_pay(wizard.batches)
        debt = total_amount_values["amount_by_default"]

        wizard.payment_difference_handling = "reconcile"
        wizard.amount = 50.0

        igtf_on_amount = 0.0
        for rec in wizard.get_moves():
            igtf_on_amount += wizard.calculate_igtf_for_payment(
                rec, wizard.amount, wizard.currency_id, wizard.payment_date,
            )
        effective_amount = abs(wizard.amount) - abs(igtf_on_amount)

        self.assertAlmostEqual(
            wizard.payment_difference, debt - effective_amount, places=2,
            msg="payment_difference must equal amount_for_difference (debt) minus effective_amount.",
        )

    def test_is_same_within_rounding_helper(self):
        """Direct unit test of the rounding-tolerance helper: a one-cent
        difference (one full VEF rounding unit) must be treated as the same
        amount, while a real, larger discrepancy must not be absorbed."""
        payment_model = self.env["account.payment"]
        comp_curr = self.currency_vef
        comp_curr.rounding = 0.01

        self.assertTrue(
            payment_model._is_same_within_rounding(21759665.40, 21759665.39, comp_curr),
            "A one-unit rounding difference must be considered the same amount.",
        )
        self.assertFalse(
            payment_model._is_same_within_rounding(21759665.40, 21730605.49, comp_curr),
            "A large, real discrepancy must not be absorbed as rounding noise.",
        )
