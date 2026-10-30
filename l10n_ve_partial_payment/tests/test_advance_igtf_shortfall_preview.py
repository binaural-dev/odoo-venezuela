from odoo.tests import tagged

from .test_partial_payment_common import PartialPaymentTestCommon


@tagged("post_install", "-at_install", "l10n_ve_partial_payment")
class TestAdvanceIgtfShortfallPreview(PartialPaymentTestCommon):
    """Coverage for ``account_move.preview_advance_igtf``.

    Every scenario here uses USD invoices/advances through
    ``bank_journal_usd`` (``is_igtf: True``), the combination that actually
    exercises ``l10n_ve_igtf``'s advance+IGTF formula -- the plain VEF
    journal used by most of ``test_partial_payment_widget.py`` never hits
    the IGTF branch at all.
    """

    def _advance_line(self, amount):
        """Post a USD advance of ``amount`` and return its outstanding
        advance-account line (customer side)."""
        payment = self._create_advance_payment(self.bank_journal_usd, amount)
        return self._outstanding_line_for_payment(payment, self.advance_cust_acc)

    def _preview(self, invoice, line, amount):
        """Call the preview as a user allowed to use partial payments."""
        return invoice.with_user(self.user_with_group).preview_advance_igtf(
            line.id, amount
        )

    # -- 1. Enough headroom in the advance: no shortfall ---------------------

    def test_advance_with_surplus_has_no_shortfall(self):
        """Advance of 150, invoice of 100, requesting 50: the advance has
        plenty of room to also absorb its own IGTF, so the full requested
        amount would land on the invoice."""
        invoice = self._create_invoice_usd(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        line = self._advance_line(150.00)

        result = self._preview(invoice, line, 50.00)

        self.assertTrue(result["applies"])
        self.assertFalse(result["shortfall"])
        self.assertAlmostEqual(result["applied_to_invoice"], 50.00, places=2)
        self.assertAlmostEqual(result["igtf"], 1.50, places=2)
        self.assertAlmostEqual(result["total_consumed"], 51.50, places=2)
        self.assertAlmostEqual(result["percentage"], self.company.igtf_percentage)

    # -- 2. Exact-amount advance, same example as the functional spec --------

    def test_advance_without_surplus_predicts_igtf_carved_from_invoice(self):
        """Advance of exactly 2.00 (3% IGTF), requesting the full 2.00: the
        advance has nothing left over for its own IGTF (0.06), so only
        1.94 would actually land on the invoice -- the exact numbers from
        the functional spec's example."""
        invoice = self._create_invoice_usd(2.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        line = self._advance_line(2.00)

        result = self._preview(invoice, line, 2.00)

        self.assertTrue(result["shortfall"])
        self.assertAlmostEqual(result["requested"], 2.00, places=2)
        self.assertAlmostEqual(result["applied_to_invoice"], 1.94, places=2)
        self.assertAlmostEqual(result["igtf"], 0.06, places=2)
        # Scenario B: the whole advance is consumed.
        self.assertAlmostEqual(result["total_consumed"], 2.00, places=2)
        self.assertEqual(result["currency_id"], invoice.currency_id.id)

    # -- 3. Parity: the preview must match what actually gets applied --------

    def test_parity_between_preview_and_real_application(self):
        """The real workhorse test: apply the same shortfall scenario for
        real (through ``js_assign_outstanding_line``, the genuine-partial
        advance branch) and confirm the invoice's residual moved by exactly
        ``real_applied`` -- not the requested amount. This is what blinds
        the preview against silently drifting out of sync with
        ``l10n_ve_igtf``'s own formula on a future change there.
        """
        invoice = self._create_invoice_usd(10.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        line = self._advance_line(2.00)

        residual_before = abs(invoice.amount_residual)
        preview = self._preview(invoice, line, 2.00)
        self.assertTrue(preview["shortfall"])

        self._apply_partial(invoice, line, 2.00)
        invoice = self.env["account.move"].browse(invoice.id)

        applied = residual_before - abs(invoice.amount_residual)
        self.assertAlmostEqual(applied, preview["applied_to_invoice"], places=2)

    def test_parity_scenario_a_amounts_match_entries(self):
        """Scenario A really applied: applied/igtf/total_consumed and the
        advance's leftover must match the preview."""
        invoice = self._create_invoice_usd(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        line = self._advance_line(51.50)
        advance_before = abs(line.amount_residual_currency)
        residual_before = abs(invoice.amount_residual)

        preview = self._preview(invoice, line, 50.00)
        self.assertFalse(preview["shortfall"])

        self._apply_partial(invoice, line, 50.00)
        invoice = self.env["account.move"].browse(invoice.id)
        line.invalidate_recordset()

        self.assertAlmostEqual(
            residual_before - abs(invoice.amount_residual),
            preview["applied_to_invoice"], places=2,
        )
        self.assertAlmostEqual(
            advance_before - abs(line.amount_residual_currency),
            preview["total_consumed"], places=2,
        )
        igtf_account = self.company.customer_account_igtf_id
        igtf_lines = self.env["account.move.line"].search([
            ("account_id", "=", igtf_account.id),
            ("partner_id", "=", self.partner.id),
            ("parent_state", "=", "posted"),
        ])
        self.assertAlmostEqual(
            sum(abs(l.amount_currency) for l in igtf_lines), preview["igtf"], places=2
        )

    # -- 4. No IGTF journal: no shortfall -------------------------------------

    def test_non_igtf_journal_has_no_shortfall(self):
        payment = self._create_advance_payment(self.bank_journal_usd_no_igtf, 2.00)
        line = self._outstanding_line_for_payment(payment, self.advance_cust_acc)
        invoice = self._create_invoice_usd(2.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        result = self._preview(invoice, line, 2.00)

        self.assertEqual(result, {"applies": False})

    def test_non_advance_line_has_no_shortfall(self):
        invoice = self._create_invoice_usd(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._create_plain_payment(self.bank_journal_usd, 100.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        result = self._preview(invoice, line, 50.00)

        self.assertEqual(result, {"applies": False})

    # -- 5. Requested amount exceeds the advance's own balance ----------------

    def test_amount_exceeding_advance_balance_still_predicts_shortfall(self):
        """Requesting 10 against a 2.00 advance (well below the 100
        invoice's residual): ``base_amount_applied`` clamps to the
        advance's own 2.00, which always lands in Escenario B once IGTF is
        added on top -- must not raise/divide by zero, and must report the
        same shortfall as requesting exactly 2.00 would."""
        invoice = self._create_invoice_usd(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        line = self._advance_line(2.00)

        result = self._preview(invoice, line, 10.00)

        self.assertTrue(result["shortfall"])
        self.assertAlmostEqual(result["applied_to_invoice"], 1.94, places=2)

    # -- 6. Full-application path (amount >= invoice residual) ---------------

    def test_full_application_amount_still_predicts_shortfall(self):
        """Typing an amount greater than or equal to the invoice's own
        residual (the "apply everything" path through the very same
        popover) must still warn: the preview clamps to the invoice
        residual internally, same as the real full-apply path does via
        ``initial_residual`` in ``l10n_ve_igtf.js_assign_outstanding_line``.
        """
        invoice = self._create_invoice_usd(2.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        line = self._advance_line(2.00)

        result = self._preview(invoice, line, 999999.00)

        self.assertTrue(result["shortfall"])
        self.assertAlmostEqual(result["applied_to_invoice"], 1.94, places=2)

    # -- 7. Unrelated company/partner advance ---------------------------------

    def test_unrelated_partner_advance_line_has_no_shortfall(self):
        """An advance line that belongs to a different partner never shows
        up in this invoice's own
        ``invoice_outstanding_credits_debits_widget_advance_payment``, so
        the lookup simply misses -- no error, just no shortfall."""
        other_partner = self.env["res.partner"].create({
            "name": "Otro Cliente",
            "property_account_receivable_id": self.acc_receivable.id,
            "property_account_payable_id": self.acc_payable.id,
            "taxpayer_type": "formal",
            "default_advance_customer_account_id": self.advance_cust_acc.id,
            "default_advance_supplier_account_id": self.advance_supp_acc.id,
        })

        invoice = self._create_invoice_usd(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        other_partner_backup, self.partner = self.partner, other_partner
        try:
            other_line = self._advance_line(2.00)
        finally:
            self.partner = other_partner_backup

        result = self._preview(invoice, other_line, 2.00)

        self.assertEqual(result, {"applies": False})

    def test_partial_payments_disabled_returns_no_preview(self):
        """With the company flag off the preview does not apply at all."""
        invoice = self._create_invoice_usd(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        line = self._advance_line(150.00)
        self.company.partial_pay_from_outstanding = False

        self.assertEqual(self._preview(invoice, line, 50.00), {"applies": False})

    def test_invalid_amount_returns_no_preview(self):
        invoice = self._create_invoice_usd(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        line = self._advance_line(150.00)

        self.assertEqual(self._preview(invoice, line, 0.0), {"applies": False})
        self.assertEqual(self._preview(invoice, line, "abc"), {"applies": False})
