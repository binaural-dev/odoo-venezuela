from odoo.tests import tagged

from .test_partial_payment_common import PartialPaymentTestCommon


@tagged("post_install", "-at_install", "l10n_ve_partial_payment")
class TestPartialPaymentForceBalance(PartialPaymentTestCommon):
    """Regression coverage for the ``force_balance`` fix documented in
    ``account_move.prepare_advance_payment_vals``.

    ``l10n_ve_igtf._create_advance_payment_move`` sets ``force_balance`` to
    the invoice's FULL residual whenever the amount about to be applied
    equals (within rounding) the amount it was asked to apply -- which is
    trivially true even for a genuinely partial request, because the caller
    already passes the partial amount as ``amount_residual``. Left
    uncorrected, the cross-entry would settle the invoice in full regardless
    of the smaller amount actually requested.

    ``prepare_advance_payment_vals`` neutralizes ``force_balance`` to
    ``None`` whenever the partial-amount context key is set, precisely to
    prevent that. This is the exact condition that triggers ``force_balance``
    upstream (``payment.currency_id == self.currency_id``): a VEF advance
    against a VEF invoice, same as ``bank_journal_bs``.
    """

    def test_successive_partials_on_same_currency_advance_do_not_force_full_balance(self):
        """VEF advance of 100 against a VEF invoice of 100, applied in three
        successive partial/full steps:

        1. First partial of 40 -- must leave residual ~60. WITHOUT this
           module's ``prepare_advance_payment_vals`` override (e.g. if the
           ``if self.env.context.get(CONTEXT_KEY) is not None and
           force_balance is not None: force_balance = None`` guard in
           ``account_move.py`` were commented out), ``force_balance`` would
           force the cross-entry to the invoice's full 100 residual and this
           FIRST ``assertAlmostEqual`` (60.0) would fail, landing on 0.0
           (fully paid) instead -- that is the bug this test protects
           against; it is not automated here (nothing in this test comments
           out production code), just documented for whoever audits it.
        2. Second partial of 30 -- residual ~30.
        3. Remaining request (>= residual): falls into the ``>=`` branch of
           ``account_move.js_assign_outstanding_line`` (plain ``super()``,
           ``force_balance`` computed normally since nothing is left to
           prorate) -- invoice ends up ``paid``.

        The advance account's own residual is checked at each step too.
        """
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_advance_payment(self.bank_journal_bs, 100.00)
        line = self._outstanding_line_for_payment(payment, self.advance_cust_acc)

        # Step 1: first partial of 40.
        self._apply_partial(invoice, line, 40.00)
        invoice = self.env["account.move"].browse(invoice.id)
        self.assertEqual(invoice.payment_state, "partial")
        self.assertAlmostEqual(invoice.amount_residual, 60.00, places=2)
        self.assertAlmostEqual(
            abs(self._advance_residual()), 60.00, places=2
        )

        # Step 2: second partial of 30, against the SAME advance's leftover
        # outstanding line (still not fully reconciled after step 1).
        line = self.env["account.move.line"].search(
            [
                ("account_id", "=", self.advance_cust_acc.id),
                ("partner_id", "=", self.partner.id),
                ("credit", ">", 0),
                ("reconciled", "=", False),
            ]
        )
        self.assertTrue(line, "El anticipo debe conservar una línea sin conciliar tras el primer parcial.")
        self._apply_partial(invoice, line, 30.00)
        invoice = self.env["account.move"].browse(invoice.id)
        self.assertEqual(invoice.payment_state, "partial")
        self.assertAlmostEqual(invoice.amount_residual, 30.00, places=2)
        self.assertAlmostEqual(
            abs(self._advance_residual()), 30.00, places=2
        )

        # Step 3: request the remaining balance (>= residual) -- falls
        # through to the plain super() path (full application).
        line = self.env["account.move.line"].search(
            [
                ("account_id", "=", self.advance_cust_acc.id),
                ("partner_id", "=", self.partner.id),
                ("credit", ">", 0),
                ("reconciled", "=", False),
            ]
        )
        self.assertTrue(line, "El anticipo debe conservar una línea sin conciliar tras el segundo parcial.")
        self._apply_partial(invoice, line, 30.00)
        invoice = self.env["account.move"].browse(invoice.id)
        self.assertIn(invoice.payment_state, ("paid", "in_payment"))

    def _advance_residual(self):
        lines = self.env["account.move.line"].search(
            [
                ("account_id", "=", self.advance_cust_acc.id),
                ("partner_id", "=", self.partner.id),
                ("credit", ">", 0),
                ("reconciled", "=", False),
            ]
        )
        return sum(lines.mapped("amount_residual"))
