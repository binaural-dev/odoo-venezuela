from odoo.tests import tagged

from .test_partial_payment_common import PartialPaymentTestCommon


@tagged("post_install", "-at_install", "l10n_ve_partial_payment")
class TestPartialPopoverData(PartialPaymentTestCommon):
    """Coverage for ``account_move.get_partial_popover_data``.

    All scenarios use USD invoices/advances through ``bank_journal_usd``
    (``is_igtf: True``, 3% IGTF). Expected values are derived from the
    formula in ``l10n_ve_igtf._create_advance_payment_move``.
    """

    def _advance_line(self, amount, journal=None):
        payment = self._create_advance_payment(journal or self.bank_journal_usd, amount)
        return self._outstanding_line_for_payment(payment, self.advance_cust_acc)

    def _posted_invoice(self, amount):
        invoice = self._create_invoice_usd(amount)
        invoice.with_context(move_action_post_alert=True).action_post()
        return invoice

    def _data(self, invoice, line):
        return invoice.with_user(self.user_with_group).get_partial_popover_data(line.id)

    def _assert_suggestion_is_exact(self, invoice_amount, advance_amount):
        """Apply the suggestion for real: no shortfall, advance nearly drained."""
        invoice = self._posted_invoice(invoice_amount)
        line = self._advance_line(advance_amount)
        data = self._data(invoice, line)
        suggested = data["suggested_amount"]
        self.assertGreater(suggested, 0.0)

        preview = invoice.with_user(self.user_with_group).preview_advance_igtf(
            line.id, suggested
        )
        if preview["applies"]:
            self.assertFalse(preview["shortfall"])

        residual_before = abs(invoice.amount_residual)
        advance_before = abs(line.amount_residual_currency)
        self._apply_partial(invoice, line, suggested)
        invoice = self.env["account.move"].browse(invoice.id)
        line.invalidate_recordset()

        self.assertAlmostEqual(
            residual_before - abs(invoice.amount_residual), suggested, places=2
        )
        consumed = advance_before - abs(line.amount_residual_currency)
        if preview["applies"]:
            self.assertAlmostEqual(consumed, preview["total_consumed"], places=2)
        # Nothing but rounding dust is left in the advance when the advance
        # (not the invoice) was the limit.
        if suggested < residual_before:
            self.assertLessEqual(abs(line.amount_residual_currency), 0.02)

    # -- Suggested amount with IGTF -------------------------------------------

    def test_suggestion_for_advance_with_igtf_fits_without_shortfall(self):
        """Advance 51.50, invoice 100, IGTF 3%: 50.00 + 1.50 = 51.50."""
        invoice = self._posted_invoice(100.00)
        line = self._advance_line(51.50)

        data = self._data(invoice, line)

        self.assertTrue(data["allowed"])
        self.assertTrue(data["igtf_applies"])
        self.assertAlmostEqual(data["igtf_rate"], self.company.igtf_percentage)
        self.assertAlmostEqual(data["suggested_amount"], 50.00, places=2)

    def test_suggestion_capped_by_invoice_residual(self):
        """Advance larger than the invoice: the residual is suggested."""
        invoice = self._posted_invoice(10.00)
        line = self._advance_line(50.00)

        data = self._data(invoice, line)

        self.assertTrue(data["igtf_applies"])
        self.assertAlmostEqual(data["suggested_amount"], 10.00, places=2)

    def test_suggestion_property_various_amounts(self):
        for advance in (51.50, 51.51, 33.33, 0.03):
            with self.subTest(advance=advance):
                self._assert_suggestion_is_exact(100.00, advance)

    def test_suggestion_after_a_first_partial_with_igtf_top(self):
        """Second partial on the same invoice (part of the IGTF already paid)."""
        invoice = self._posted_invoice(100.00)
        first = self._advance_line(200.00)
        self._apply_partial(invoice, first, 40.00)
        invoice = self.env["account.move"].browse(invoice.id)

        second = self._advance_line(61.00)
        data = self._data(invoice, second)
        suggested = data["suggested_amount"]
        self.assertGreater(suggested, 0.0)

        preview = invoice.with_user(self.user_with_group).preview_advance_igtf(
            second.id, suggested
        )
        if preview["applies"]:
            self.assertFalse(preview["shortfall"])
        residual_before = abs(invoice.amount_residual)
        self._apply_partial(invoice, second, suggested)
        invoice = self.env["account.move"].browse(invoice.id)
        second.invalidate_recordset()

        self.assertAlmostEqual(
            residual_before - abs(invoice.amount_residual), suggested, places=2
        )
        self.assertLessEqual(abs(second.amount_residual_currency), 0.02)

    # -- No IGTF / not resolvable ---------------------------------------------

    def test_no_igtf_journal_suggests_min_of_available_and_residual(self):
        invoice = self._posted_invoice(100.00)
        line = self._advance_line(51.50, journal=self.bank_journal_usd_no_igtf)

        data = self._data(invoice, line)

        self.assertTrue(data["allowed"])
        self.assertFalse(data["igtf_applies"])
        self.assertEqual(data["igtf_rate"], 0.0)
        self.assertAlmostEqual(data["suggested_amount"], 51.50, places=2)

    def test_plain_payment_line_has_no_igtf(self):
        invoice = self._posted_invoice(100.00)
        payment = self._create_plain_payment(self.bank_journal_usd_no_igtf, 40.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        data = self._data(invoice, line)

        self.assertFalse(data["igtf_applies"])
        self.assertAlmostEqual(data["suggested_amount"], 40.00, places=2)

    def test_unrelated_line_exposes_nothing(self):
        invoice = self._posted_invoice(100.00)
        other_partner = self.env["res.partner"].create({
            "name": "Otro Cliente",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id,
            "taxpayer_type": "formal",
            "default_advance_customer_account_id": self.advance_cust_acc.id,
            "default_advance_supplier_account_id": self.advance_supp_acc.id,
        })
        backup, self.partner = self.partner, other_partner
        try:
            other_line = self._advance_line(30.00)
        finally:
            self.partner = backup

        data = self._data(invoice, other_line)

        self.assertFalse(data["igtf_applies"])
        self.assertEqual(data["igtf_rate"], 0.0)
        self.assertEqual(data["suggested_amount"], 0.0)

    def test_not_allowed_when_company_flag_is_off(self):
        invoice = self._posted_invoice(100.00)
        line = self._advance_line(51.50)
        self.company.partial_pay_from_outstanding = False

        data = self._data(invoice, line)

        self.assertFalse(data["allowed"])
        self.assertFalse(data["igtf_applies"])
