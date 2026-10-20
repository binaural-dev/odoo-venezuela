from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.l10n_ve_accountant.tests.test_indexed_payments import TestIndexedPayments


@tagged("post_install", "-at_install", "l10n_ve_igtf_zero_amount_payment")
class TestIgtfZeroAmountPayment(TestIndexedPayments):
    """Una factura en Bs menor a 0,01 USD pagada con un diario USD con IGTF
    (caso Zelle) redondea a 0,00 USD: el wizard debe bloquearse sin dejar
    pagos creados ni conciliados."""

    def setUp(self):
        super().setUp()
        self.company.igtf_percentage = 3.0

    def _create_igtf_wizard(self, invoice):
        wizard = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=invoice.ids, active_id=invoice.id,
        ).create(
            {
                "journal_id": self._get_foreign_bank_journal(self.currency_usd).id,
                "currency_id": self.currency_usd.id,
                "payment_date": self.payment_date,
            }
        )
        wizard.is_igtf = True
        return wizard

    def test_wizard_igtf_usd_amount_rounded_to_zero_is_blocked(self):
        self._set_rate(self.currency_usd, self.invoice_date, 40.0)
        self._set_rate(self.currency_usd, self.payment_date, 40.0)

        # 0,10 Bs / 40 Bs por USD = 0,0025 USD, que redondea a 0,00 USD
        invoice = self._create_vef_invoice(amount=0.1)
        residual = invoice.amount_residual
        payments_before = self.env["account.payment"].search_count([])
        wizard = self._create_igtf_wizard(invoice)
        self.assertTrue(wizard.currency_id.is_zero(wizard.amount))

        with self.assertRaises(UserError):
            with self.cr.savepoint():
                wizard.action_create_payments()

        self.assertEqual(self.env["account.payment"].search_count([]), payments_before)
        self.assertEqual(invoice.amount_residual, residual)
        self.assertNotEqual(invoice.payment_state, "paid")
        self.assertFalse(
            invoice.line_ids.filtered(
                lambda l: l.account_id.account_type == "asset_receivable"
            ).matched_credit_ids
        )
