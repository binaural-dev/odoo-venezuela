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
        self.assertAlmostEqual(wizard.amount, 103.0, 2)

        # The payment is created on another request, where the IGTF of the
        # wizard is computed again.
        wizard.invalidate_recordset()
        action = wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.assertAlmostEqual(payment.amount, 103.0, 2)
        self.assertAlmostEqual(
            payment.igtf_amount, 3.0, 2, "The IGTF must be 3% of the 100.00 paid, not of the 120.00 invoiced."
        )
        self.assertAlmostEqual(invoice.amount_residual, invoice.amount_total - 100.0, 2)

    def test_igtf_added_to_the_typed_amount_before_other_currencies(self):
        """The amount typed in foreign currency is paid to the invoice and the
        IGTF is added on top of it, so paying first in dollars and then in
        bolivars charges the same as the other way round."""
        invoice = self._create_invoice_usd(120.0)
        invoice.with_context(move_action_post_alert=True).action_post()

        payment = self._register_payment(invoice, self.bank_journal_usd, 100.0)
        self.assertAlmostEqual(payment.amount, 103.0, 2)
        self.assertAlmostEqual(payment.igtf_amount, 3.0, 2)
        self.assertAlmostEqual(invoice.amount_residual, invoice.amount_total - 100.0, 2)

        self._register_payment(invoice, self.bank_journal_bs)
        self.assertEqual(invoice.payment_state, "paid")

    def test_igtf_added_to_the_proposed_amount_after_other_currencies(self):
        """Paying first in bolivars and then the residual in dollars adds the
        IGTF of the residual to the amount proposed."""
        invoice = self._create_invoice_usd(120.0)
        invoice.with_context(move_action_post_alert=True).action_post()

        self._register_payment(invoice, self.bank_journal_bs, round(20.0 * self.rate, 2))
        residual = invoice.amount_residual
        payment = self._register_payment(invoice, self.bank_journal_usd)
        self.assertAlmostEqual(payment.igtf_amount, residual * 0.03, 2)
        self.assertAlmostEqual(payment.amount, residual * 1.03, 2)
        self.assertEqual(invoice.payment_state, "paid")
