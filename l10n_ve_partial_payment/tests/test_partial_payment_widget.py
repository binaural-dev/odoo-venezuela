from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools.misc import formatLang

from .test_partial_payment_common import PartialPaymentTestCommon


def _normalize_nbsp(text):
    """Collapse both a literal NBSP char and the ``&nbsp;`` HTML entity to a
    plain space, so a ``formatLang`` string (raw ``\\xa0``) can be compared
    against a chatter message's ``body`` (HTML-sanitized on ``message_post``,
    which re-encodes ``\\xa0`` as the ``&nbsp;`` entity) without depending on
    which of the two representations is currently in play.

    ``str(text)`` first: ``body`` is a ``markupsafe.Markup`` instance, whose
    ``.replace()`` HTML-escapes its ARGUMENTS before matching (so searching
    for the literal ``"&nbsp;"`` pattern would actually search for
    ``"&amp;nbsp;"`` and never match) -- coercing to a plain ``str`` first
    sidesteps that escaping wrapper entirely."""
    return str(text).replace("\xa0", " ").replace("&nbsp;", " ")


@tagged("post_install", "-at_install", "l10n_ve_partial_payment")
class TestPartialPaymentWidget(PartialPaymentTestCommon):
    """Functional coverage of ``account_move.js_assign_outstanding_line``'s
    partial-amount routing and its audit trail.

    Everything here uses ``bank_journal_bs`` (VEF/VEF, ``is_igtf: False``)
    unless a test says otherwise, so none of these assertions get
    contaminated by IGTF's own amount/line bookkeeping -- that belongs to
    ``l10n_ve_igtf``'s and ``l10n_ve_igtf_note_debit``'s own test suites.
    """

    # -- 1. Plain payment, genuine partial ---------------------------------

    def test_plain_payment_partial_leaves_outstanding_line_with_residual(self):
        """Loose payment for MORE than the requested partial amount: only
        the requested amount gets applied, and the payment's own
        outstanding line keeps the rest as residual (not fully consumed).

        Uses a 70 payment against a 100 invoice, applying 40 -- if the
        payment amount matched the requested amount exactly (e.g. 40/40)
        the outstanding line would end up fully reconciled by construction
        regardless of the partial-amount routing, which would not actually
        exercise "leftover on the outstanding line" the way this test name
        promises.
        """
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_plain_payment(self.bank_journal_bs, 70.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)
        self.assertTrue(line)

        self._apply_partial(invoice, line, 40.00)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertEqual(invoice.payment_state, "partial")
        self.assertAlmostEqual(invoice.amount_residual, 60.00, places=2)

        line = self.env["account.move.line"].browse(line.id)
        self.assertFalse(line.reconciled)
        self.assertAlmostEqual(abs(line.amount_residual), 30.00, places=2)

    # -- 2. Advance payment, genuine partial --------------------------------

    def test_advance_payment_partial_leaves_advance_with_residual(self):
        """Full 100 advance applied for only 40 of it against a 100 invoice:
        the invoice ends up ``partial`` with 60 residual, and the advance
        account line keeps its own 60 unconsumed -- confirms the advance
        branch does not silently apply the full advance regardless of the
        requested amount."""
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_advance_payment(self.bank_journal_bs, 100.00)
        line = self._outstanding_line_for_payment(payment, self.advance_cust_acc)
        self.assertTrue(line)

        self._apply_partial(invoice, line, 40.00)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertEqual(invoice.payment_state, "partial")
        self.assertAlmostEqual(invoice.amount_residual, 60.00, places=2)

        advance_line = self.env["account.move.line"].search(
            [
                ("account_id", "=", self.advance_cust_acc.id),
                ("partner_id", "=", self.partner.id),
                ("credit", ">", 0),
                ("reconciled", "=", False),
            ]
        )
        self.assertTrue(advance_line, "El anticipo debe conservar residual sin consumir.")
        self.assertAlmostEqual(abs(sum(advance_line.mapped("amount_residual"))), 60.00, places=2)

    # -- 3/4. Full-amount requests fall through to super() ------------------

    def test_requested_amount_equal_to_residual_uses_core_path_no_audit(self):
        """Requesting exactly the invoice's residual is treated as a full
        application (``>=`` branch): behaves like unmodified ``l10n_ve_igtf``
        (plain ``super()``), and does NOT post the partial-payment audit
        message."""
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        messages_before = len(invoice.message_ids)

        payment = self._create_plain_payment(self.bank_journal_bs, 100.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        self._apply_partial(invoice, line, 100.00)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertIn(invoice.payment_state, ("paid", "in_payment"))
        self._assert_no_audit_message(invoice, messages_before)

    def test_requested_amount_greater_than_residual_uses_core_path_no_audit(self):
        """Requesting more than the residual is also treated as full (the
        excess gets clamped downstream by the core, same as unmodified
        ``l10n_ve_igtf``): no audit message either."""
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        messages_before = len(invoice.message_ids)

        payment = self._create_plain_payment(self.bank_journal_bs, 150.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        self._apply_partial(invoice, line, 150.00)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertIn(invoice.payment_state, ("paid", "in_payment"))
        self._assert_no_audit_message(invoice, messages_before)

    def test_no_context_key_behaves_like_core_no_audit(self):
        """Without ``CONTEXT_KEY`` in the call's context at all (not even a
        falsy value), the whole partial mechanism is bypassed via the
        ``raw_amount is None`` guard -- full core behavior, no audit."""
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        messages_before = len(invoice.message_ids)

        payment = self._create_plain_payment(self.bank_journal_bs, 100.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        invoice.with_user(self.user_with_group).js_assign_outstanding_line(line.id)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertIn(invoice.payment_state, ("paid", "in_payment"))
        self._assert_no_audit_message(invoice, messages_before)

    # -- 6/7. Invalid amounts -------------------------------------------

    def test_zero_amount_raises_user_error(self):
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._create_plain_payment(self.bank_journal_bs, 100.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        with self.assertRaises(UserError):
            self._apply_partial(invoice, line, 0.0)

    def test_negative_amount_raises_user_error(self):
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._create_plain_payment(self.bank_journal_bs, 100.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        with self.assertRaises(UserError):
            self._apply_partial(invoice, line, -10.0)

    def test_amount_below_rounding_precision_raises_user_error(self):
        """0.004 on a VEF invoice (``rounding=0.01``) rounds down to zero
        under ``float_compare``'s precision, falling into the same "amount
        <= 0" branch as an explicit zero."""
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._create_plain_payment(self.bank_journal_bs, 100.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        with self.assertRaises(UserError):
            self._apply_partial(invoice, line, 0.004)

    # -- 8/9. Cosmetic-bypass documentation ----------------------------------

    def test_flag_off_ignores_requested_amount_and_applies_full_silently(self):
        """Company flag off, but the context key IS set (simulating a direct
        RPC call bypassing the disabled JS popover) and the acting user DOES
        have the group: the gate still blocks the partial routing (flag is
        the other half of the AND), so the call falls through to full
        application without raising -- this is the "cosmetic bypass"
        documented in the module's docstring: nothing stops a full apply,
        the server just never partially prorates when the flag is off."""
        self.company.partial_pay_from_outstanding = False
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._create_plain_payment(self.bank_journal_bs, 100.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        self._apply_partial(invoice, line, 40.00)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertIn(invoice.payment_state, ("paid", "in_payment"))
        self.assertAlmostEqual(invoice.amount_residual, 0.0, places=2)

    def test_user_without_group_ignores_requested_amount_and_applies_full_silently(self):
        """Same "cosmetic bypass" as above, but from the other half of the
        AND gate: flag on, context key set, but the acting user lacks
        ``group_partial_payment_apply``."""
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._create_plain_payment(self.bank_journal_bs, 100.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        self._apply_partial(invoice, line, 40.00, user=self.user_without_group)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertIn(invoice.payment_state, ("paid", "in_payment"))
        self.assertAlmostEqual(invoice.amount_residual, 0.0, places=2)

    # -- 10. Audit message content -------------------------------------------

    def test_audit_message_reports_applied_and_remaining_amounts(self):
        """A genuine partial application posts exactly one new chatter
        message whose body mentions both the applied amount and the
        remaining balance -- computed here from the same values the
        production code reads (``residual_before``/``amount_residual``
        after), formatted with ``formatLang`` like the production code
        does, rather than hardcoding a full-string comparison (which would
        be brittle against the active language)."""
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()
        messages_before = len(invoice.message_ids)

        payment = self._create_plain_payment(self.bank_journal_bs, 70.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        self._apply_partial(invoice, line, 40.00)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertEqual(len(invoice.message_ids), messages_before + 1)

        audit_message = invoice.message_ids.sorted("id")[-1]
        body = _normalize_nbsp(audit_message.body)
        expected_applied = _normalize_nbsp(
            formatLang(self.env, 40.00, currency_obj=invoice.currency_id)
        )
        expected_remaining = _normalize_nbsp(
            formatLang(self.env, 60.00, currency_obj=invoice.currency_id)
        )
        self.assertIn(expected_applied, body)
        self.assertIn(expected_remaining, body)

    # -- 11. Advance with less available than requested ----------------------

    def test_advance_with_less_available_than_requested_clamps_to_advance(self):
        """Advance of 50 against a 100 invoice, requesting 80: only 50 (the
        advance's own available amount) can actually be applied -- the
        clamp lives in ``l10n_ve_igtf._create_advance_payment_move``
        (``base_amount_applied = min(advance_amount_residual, advance_amount)``),
        not in this module. The audit message must reflect the amount
        ACTUALLY applied (50), not the 80 requested."""
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_advance_payment(self.bank_journal_bs, 50.00)
        line = self._outstanding_line_for_payment(payment, self.advance_cust_acc)

        self._apply_partial(invoice, line, 80.00)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertAlmostEqual(invoice.amount_residual, 50.00, places=2)

        audit_message = invoice.message_ids.sorted("id")[-1]
        body = _normalize_nbsp(audit_message.body)
        expected_applied = _normalize_nbsp(
            formatLang(self.env, 50.00, currency_obj=invoice.currency_id)
        )
        self.assertIn(expected_applied, body)
        self.assertNotIn(
            _normalize_nbsp(formatLang(self.env, 80.00, currency_obj=invoice.currency_id)),
            body,
        )

    # -- 12. Plain payment with less outstanding than requested --------------

    def test_plain_payment_with_less_outstanding_than_requested_clamps_and_reconciles(self):
        """Loose payment of 30 against a 100 invoice, requesting 60: only the
        30 actually available on the outstanding line gets applied (capped
        by ``account_move_line._prepare_reconciliation_amls``), which fully
        consumes that line."""
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_plain_payment(self.bank_journal_bs, 30.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        self._apply_partial(invoice, line, 60.00)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertEqual(invoice.payment_state, "partial")
        self.assertAlmostEqual(invoice.amount_residual, 70.00, places=2)

        line = self.env["account.move.line"].browse(line.id)
        self.assertTrue(line.reconciled)

    # -- 13. Vendor invoice, payable side ------------------------------------

    def test_vendor_invoice_plain_payment_partial(self):
        """Payable-side mirror of the first test: exercises the negative
        ``sign``/``balance`` branch of
        ``account_move_line._prepare_reconciliation_amls`` (payable lines
        carry the opposite sign convention from receivable ones)."""
        invoice = self._create_invoice_in_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": "supplier",
                "partner_id": self.partner.id,
                "amount": 70.00,
                "journal_id": self.bank_journal_bs.id,
            }
        )
        payment.action_post()
        line = payment.move_id.line_ids.filtered(
            lambda l: l.account_id == self.acc_payable and l.debit > 0
        )
        self.assertTrue(line, "El pago al proveedor debe dejar una línea CxP sin conciliar.")

        self._apply_partial(invoice, line, 40.00)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertEqual(invoice.payment_state, "partial")
        self.assertAlmostEqual(abs(invoice.amount_residual), 60.00, places=2)

    # -- 14. Scope of the cap in _prepare_reconciliation_amls -----------------

    def test_partial_on_one_invoice_does_not_affect_another(self):
        """Two independent invoices/payments, each with its own genuine
        partial application: confirms the ``move_id``/``line_id`` context
        pair that scopes the cap in
        ``account_move_line._prepare_reconciliation_amls`` is set fresh
        for each call (``self.with_context(move_id=self.id, line_id=line_id)``
        in ``account_move.js_assign_outstanding_line``) and never bleeds
        from one (invoice, outstanding line) pair into another.

        A direct unit call to ``_prepare_reconciliation_amls`` with a
        hand-built ``values_list`` (as suggested as the "precise" option)
        would need a realistic reconciliation candidate dict, which is
        fragile to hand-construct and easily fails for reasons unrelated to
        the guard being tested (e.g. missing keys the core's own
        exchange-difference computation expects). This integration variant
        instead proves the practical guarantee end-to-end: applying a
        partial amount to invoice B, right after doing the same to invoice
        A, must reflect ONLY invoice B's own requested amount -- if the
        move_id/line_id scoping leaked, one invoice's cap could bleed into
        the other's amounts.
        """
        invoice_a = self._create_invoice_vef(100.00)
        invoice_a.with_context(move_action_post_alert=True).action_post()
        payment_a = self._create_plain_payment(self.bank_journal_bs, 70.00)
        line_a = self._outstanding_line_for_payment(payment_a, self.acc_receivable)
        self._apply_partial(invoice_a, line_a, 40.00)

        invoice_b = self._create_invoice_vef(100.00)
        invoice_b.with_context(move_action_post_alert=True).action_post()
        payment_b = self._create_plain_payment(self.bank_journal_bs, 70.00)
        line_b = self._outstanding_line_for_payment(payment_b, self.acc_receivable)
        self._apply_partial(invoice_b, line_b, 25.00)

        invoice_a = self.env["account.move"].browse(invoice_a.id)
        invoice_b = self.env["account.move"].browse(invoice_b.id)

        self.assertAlmostEqual(invoice_a.amount_residual, 60.00, places=2)
        self.assertAlmostEqual(invoice_b.amount_residual, 75.00, places=2)

    # -- 15. res.config.settings ---------------------------------------------

    def test_res_config_settings_writes_through_to_company(self):
        """The ``related``/``readonly=False`` field on ``res.config.settings``
        must actually persist to ``res.company`` on ``execute()``."""
        self.company.partial_pay_from_outstanding = False
        self.env["res.config.settings"].create(
            {"partial_pay_from_outstanding": True}
        ).execute()
        self.assertTrue(self.company.partial_pay_from_outstanding)

    # -- helpers --------------------------------------------------------------

    def _assert_no_audit_message(self, invoice, messages_before):
        self.assertEqual(
            len(invoice.message_ids),
            messages_before,
            "No debe postearse el mensaje de auditoría de aplicación parcial "
            "cuando la llamada se resolvió por la rama super()/core.",
        )
        self.assertFalse(
            any("Partial payment applied" in (m.body or "") for m in invoice.message_ids),
        )
