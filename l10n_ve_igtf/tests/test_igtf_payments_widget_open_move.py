from odoo.tests import tagged

from odoo.addons.l10n_ve_accountant.tests.test_indexed_payments import TestIndexedPayments


@tagged("post_install", "-at_install", "l10n_ve_igtf_open_payment")
class TestIgtfPaymentsWidgetOpenMove(TestIndexedPayments):
    """The popover of the payments of an invoice shows the native "View" button
    only if the payment line carries can_open_move. l10n_ve_igtf extends the
    widget calling super(), so it must keep every key account computes."""

    def _paid_invoice(self):
        self._set_rate(self.currency_usd, self.invoice_date, 40.0)
        self._set_rate(self.currency_usd, self.payment_date, 40.0)
        invoice = self._create_vef_invoice(amount=100.0)
        wizard = self._register_payment(invoice, self.currency_usd, True)
        wizard.action_create_payments()
        invoice.invalidate_recordset()
        return invoice

    def test_reconciled_payments_widget_can_open_move(self):
        widget = self._paid_invoice().invoice_payments_widget
        self.assertTrue(widget and widget.get("content"), "no reconciled payments")
        for payment in widget["content"]:
            with self.subTest(payment=payment.get("name")):
                self.assertIn("can_open_move", payment)
                # the entry of a payment (origin_payment_id) can always be opened
                self.assertTrue(payment["can_open_move"])
                self.assertTrue(payment["account_payment_id"])

    def test_draft_invoice_has_no_payments_widget(self):
        invoice = self._paid_invoice()
        invoice.button_draft()
        invoice.invalidate_recordset()
        self.assertFalse(invoice.invoice_payments_widget)
