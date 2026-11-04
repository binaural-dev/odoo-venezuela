from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tests.common import Form

from .test_common_sale_book_igtf_usd_partner_formal import IGTFTestCommonSaleBook


@tagged("igtf_run", "-at_install", "post_install")
class TestPaymentRegisterPartialIgtf(IGTFTestCommonSaleBook):

    def _register_payment(self, invoice, journal, amount=None):
        action_data = invoice.action_register_payment()
        with Form(
            self.env["account.payment.register"].with_context(**action_data["context"])
        ) as pay_form:
            pay_form.journal_id = journal
            if amount is not None:
                pay_form.amount = amount
        action = pay_form.record.action_create_payments()
        return self.env["account.payment"].browse(action.get("res_id"))

    def _assert_igtf_residual(self, payment, igtf):
        """The IGTF is inside the payment entry: a receivable of the customer
        left open and the IGTF line, while the liquidity line is the amount
        of the payment."""
        lines = payment.move_id.line_ids
        residual_line = lines.filtered("is_igtf_residual")
        igtf_line = lines.filtered(lambda l: l.account_id == self.company.customer_account_igtf_id)
        self.assertEqual(len(residual_line), 1)
        self.assertEqual(residual_line.account_id, payment.destination_account_id)
        self.assertAlmostEqual(residual_line.amount_currency, igtf, 2)
        self.assertAlmostEqual(residual_line.amount_residual_currency, igtf, 2)
        self.assertAlmostEqual(igtf_line.amount_currency, -igtf, 2)
        liquidity_line = payment._seek_for_lines()[0]
        self.assertAlmostEqual(liquidity_line.amount_currency, payment.amount, 2)
        return residual_line

    def test_igtf_from_typed_amount_after_changing_the_date(self):
        """Regression: an amount lower than the invoice typed in the wizard,
        followed by a change that recomputes the wizard (date, journal or
        rate), must keep the IGTF of the amount paid when the payment is
        created, not take it from the whole residual of the invoice."""
        yesterday = fields.Date.today() - timedelta(days=1)
        self.currency_vef.write(
            {"rate_ids": [Command.create({"company_rate": self.rate, "name": yesterday})]}
        )
        invoice = self._create_invoice_usd(120.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        action_data = invoice.action_register_payment()

        with Form(
            self.env["account.payment.register"].with_context(**action_data["context"])
        ) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            pay_form.payment_date = fields.Date.today()
            pay_form.amount = 100.0
            pay_form.payment_date = yesterday
        wizard = pay_form.record
        self.assertAlmostEqual(wizard.igtf_amount, 3.0, 2)
        self.assertAlmostEqual(
            wizard.amount, 100.0, 2, "The amount typed in the wizard must not be changed by the IGTF."
        )
        self.assertAlmostEqual(wizard.amount_without_difference, 100.0, 2)
        self.assertAlmostEqual(wizard.payment_difference, 20.0, 2)

        # The payment is created on another request, where the IGTF of the
        # wizard is computed again.
        wizard.invalidate_recordset()
        action = wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.assertAlmostEqual(payment.amount, 100.0, 2)
        self.assertAlmostEqual(
            payment.igtf_amount, 3.0, 2, "The IGTF must be 3% of the 100.00 paid, not of the 120.00 invoiced."
        )
        self._assert_igtf_residual(payment, 3.0)
        self.assertAlmostEqual(invoice.amount_residual, invoice.amount_total - 100.0, 2)

    def test_igtf_left_as_residual_of_the_typed_amount(self):
        """The amount typed in foreign currency is the payment and is paid to
        the invoice: the IGTF is charged to the customer as an open receivable
        of the payment entry, so paying first in dollars and then in bolivars
        pays the invoice and leaves only the IGTF to collect."""
        invoice = self._create_invoice_usd(120.0)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._register_payment(invoice, self.bank_journal_usd, 100.0)
        self.assertAlmostEqual(payment.amount, 100.0, 2)
        self.assertAlmostEqual(payment.igtf_amount, 3.0, 2)
        self._assert_igtf_residual(payment, 3.0)
        self.assertAlmostEqual(invoice.amount_residual, invoice.amount_total - 100.0, 2)

        self._register_payment(invoice, self.bank_journal_bs)
        self.assertEqual(invoice.payment_state, "paid")
        self.assertAlmostEqual(invoice.bi_igtf, 100.0, 2)

    def test_payment_in_bolivars_greater_than_the_invoice_keeps_its_amount(self):
        """A payment greater than the residual of the invoice, on the date of the invoice,
        keeps its amount in company currency: only a rounding difference with the residual is
        adjusted, the rest is left open to the customer."""
        invoice = self._create_invoice_usd(120.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        amount_bs = round(150.0 * self.rate, 2)

        context = invoice.action_register_payment()["context"]
        with Form(self.env["account.payment.register"].with_context(**context)) as pay_form:
            pay_form.journal_id = self.bank_journal_bs
            pay_form.payment_date = invoice.invoice_date
            pay_form.amount = amount_bs
        payment = self.env["account.payment"].browse(
            pay_form.record.action_create_payments().get("res_id")
        )
        liquidity_line = payment._seek_for_lines()[0]
        self.assertAlmostEqual(liquidity_line.amount_currency, amount_bs, 2)
        self.assertAlmostEqual(abs(liquidity_line.balance), 150.0, 2)
        self.assertEqual(invoice.payment_state, "paid")

    def test_igtf_residual_paid_apart(self):
        """The IGTF left as a residual of the customer is paid apart, without
        IGTF on it, and the payment of the invoice ends reconciled."""
        invoice = self._create_invoice_usd(120.0)
        invoice.with_context(move_action_post_alert=True).action_post()
        payment = self._register_payment(invoice, self.bank_journal_usd)
        residual_line = self._assert_igtf_residual(payment, 3.6)
        self.assertEqual(invoice.payment_state, "paid")
        self.assertFalse(payment.is_reconciled)

        action_data = residual_line.action_register_payment()
        context = dict(action_data["context"], active_id=residual_line.id)
        with Form(self.env["account.payment.register"].with_context(**context)) as pay_form:
            pay_form.journal_id = self.bank_journal_usd
            self.assertAlmostEqual(pay_form.amount, 3.6, 2)
            self.assertFalse(pay_form.is_igtf)
        igtf_payment = self.env["account.payment"].browse(
            pay_form.record.action_create_payments().get("res_id")
        )
        self.assertAlmostEqual(igtf_payment.amount, 3.6, 2)
        self.assertFalse(igtf_payment.igtf_amount)
        self.assertTrue(residual_line.reconciled)
        self.assertTrue(payment.is_reconciled)

    def test_igtf_left_as_residual_of_the_proposed_amount(self):
        """Paying first in bolivars and then the residual in dollars: the payment
        is the residual of the invoice and the IGTF of it is left to collect."""
        invoice = self._create_invoice_usd(120.0)
        invoice.with_context(move_action_post_alert=True).action_post()

        self._register_payment(invoice, self.bank_journal_bs, round(20.0 * self.rate, 2))
        residual = invoice.amount_residual
        payment = self._register_payment(invoice, self.bank_journal_usd)
        self.assertAlmostEqual(payment.igtf_amount, residual * 0.03, 2)
        self.assertAlmostEqual(payment.amount, residual, 2)
        self._assert_igtf_residual(payment, residual * 0.03)
        self.assertEqual(invoice.payment_state, "paid")
