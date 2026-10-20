from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tests.common import Form

from .test_common_sale_book_igtf_usd_partner_formal import IGTFTestCommonSaleBook


@tagged("igtf_run", "-at_install", "post_install")
class TestPaymentRegisterPartialIgtf(IGTFTestCommonSaleBook):

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

        # The payment is created on another request, where the IGTF of the
        # wizard is computed again.
        wizard.invalidate_recordset()
        action = wizard.action_create_payments()
        payment = self.env["account.payment"].browse(action.get("res_id"))

        self.assertAlmostEqual(payment.amount, 100.0, 2)
        self.assertAlmostEqual(
            payment.igtf_amount, 3.0, 2, "The IGTF must be 3% of the 100.00 paid, not of the 120.00 invoiced."
        )
        self.assertAlmostEqual(invoice.amount_residual, invoice.amount_total - 97.0, 2)
