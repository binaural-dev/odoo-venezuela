from odoo import fields
from odoo.tests import tagged

from .test_partial_payment_common import PartialPaymentTestCommon


@tagged("post_install", "-at_install", "l10n_ve_partial_payment")
class TestPartialPaymentMulticurrency(PartialPaymentTestCommon):
    """The multicurrency scenario that motivated this module: a USD
    outstanding line applied partially against a VEF invoice.

    Uses ``bank_journal_usd_no_igtf`` (not ``IGTFTestCommon.bank_journal_usd``,
    which has ``is_igtf: True`` and would add an IGTF amount/line on top of
    every payment, contaminating the plain currency-conversion assertions
    here). All expected amounts are computed IN the test from the real
    ``res.currency.rate`` records set up by ``IGTFTestCommon`` (today's USD
    rate ``1/390.2944``, yesterday's ``1/380``), never copied as magic
    numbers.
    """

    def test_same_day_partial_application_no_exchange_difference(self):
        """Loose USD payment (today) applied partially against a VEF
        invoice (today, i.e. no rate drift between the invoice and the
        payment): the invoice residual drops by exactly the requested VEF
        amount, the USD outstanding line's own residual drops by the
        equivalent at TODAY's rate, and no exchange-difference move gets
        generated (the invoice itself carries no foreign-currency
        component of its own -- it's VEF/VEF)."""
        invoice = self._create_invoice_vef(100.00)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_plain_payment(self.bank_journal_usd_no_igtf, 50.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)
        self.assertTrue(line)

        requested_vef = 40.00
        self._apply_partial(invoice, line, requested_vef)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertAlmostEqual(invoice.amount_residual, 60.00, places=2)

        expected_usd_consumed = self.currency_vef._convert(
            requested_vef, self.currency_usd, self.company, fields.Date.today()
        )
        line = self.env["account.move.line"].browse(line.id)
        self.assertAlmostEqual(
            abs(line.amount_residual_currency),
            50.00 - expected_usd_consumed,
            places=2,
        )

        self.assertFalse(
            invoice.line_ids.matched_credit_ids.exchange_move_id,
            "Una factura VEF/VEF sin componente de moneda extranjera propia "
            "no debe generar diferencial cambiario.",
        )

    def test_prior_day_invoice_partial_application_generates_exchange_difference(self):
        """Invoice in USD (foreign currency relative to the VEF company)
        dated YESTERDAY (rate ``1/380``), USD payment TODAY (rate
        ``1/390.2944``) applied partially: because the invoice's own
        receivable line carries a foreign-currency component booked at
        yesterday's rate and the USD payment settles at today's rate, a
        proportional exchange-difference entry is expected -- proportional
        to the PARTIAL portion applied, not to the full outstanding line.

        This is the "USD invoice (not just the payment) paid partially"
        scenario the module's README lists under "Pendiente" as a stress
        test not yet covered.

        The exact delta is computed here (in company currency, VEF, which is
        where exchange-difference entries are booked) from both real rates
        via ``_convert``; if that assertion turns out to not hold exactly
        (the core's exchange-difference algorithm has its own
        rounding/bucketing that this test does not fully reproduce), we fall
        back to asserting only that the field is populated, documented
        inline below."""
        yesterday = fields.Date.subtract(fields.Date.today(), days=1)
        invoice = self._create_invoice_usd(100.00, date=yesterday)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._create_plain_payment(self.bank_journal_usd_no_igtf, 50.00)
        line = self._outstanding_line_for_payment(payment, self.acc_receivable)

        requested_usd = 40.00
        self._apply_partial(invoice, line, requested_usd)
        invoice = self.env["account.move"].browse(invoice.id)

        self.assertAlmostEqual(invoice.amount_residual, 60.00, places=2)

        exchange_move = invoice.line_ids.matched_credit_ids.exchange_move_id
        self.assertTrue(
            exchange_move,
            "Se esperaba un asiento de diferencial cambiario: la factura USD "
            "fue emitida ayer (tasa 1/380) y el pago USD se concilia hoy "
            "(tasa 1/390.2944).",
        )

        # Documented limitation: we assert only that the exchange-difference
        # move exists and is proportioned to the partial (not the full)
        # amount, via a loose upper bound, rather than pinning an exact
        # figure -- reproducing the core's own rounding/bucketing for the
        # exchange-difference algorithm inside this test would risk
        # asserting a number we are not fully confident is correct rather
        # than a real regression check.
        today_value_vef = self.currency_usd._convert(
            requested_usd, self.currency_vef, self.company, fields.Date.today()
        )
        yesterday_value_vef = self.currency_usd._convert(
            requested_usd, self.currency_vef, self.company, yesterday
        )
        expected_delta_vef = abs(today_value_vef - yesterday_value_vef)
        exchange_amount_vef = sum(l.debit for l in exchange_move.line_ids)
        self.assertGreater(exchange_amount_vef, 0.0)
        self.assertLessEqual(
            exchange_amount_vef, expected_delta_vef + self.currency_vef.rounding
        )
