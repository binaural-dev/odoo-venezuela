from odoo.tests import tagged

from odoo.addons.l10n_ve_accountant.tests.test_indexed_payments import TestIndexedPayments


@tagged("post_install", "-at_install", "l10n_ve_igtf_payment_force_balance")
class TestIgtfPaymentForceBalance(TestIndexedPayments):
    """``force_balance`` de ``account.payment.create``: un pago creado fuera del
    wizard con su propio balance en Bs lo conserva (el cierre del PdV de una
    caja en otra moneda lo crea así, con lo cobrado a la tasa de la caja); en
    un pago del wizard se sigue descartando y el pago va a la tasa de su fecha
    (pagos indexados)."""

    def _create_usd_payment(self, force_balance, **extra):
        return self.env["account.payment"].create({
            "payment_type": "inbound",
            "partner_type": "customer",
            "partner_id": self.partner.id,
            "amount": 100.0,
            "currency_id": self.currency_usd.id,
            "journal_id": self._get_foreign_bank_journal(self.currency_usd).id,
            "payment_method_line_id": self.pm_line_in.id,
            "outstanding_account_id": self.account_bank.id,
            "destination_account_id": self.account_receivable.id,
            "date": self.payment_date,
            "force_balance": force_balance,
            **extra,
        })

    def _balances(self, payment):
        liquidity, counterpart, _writeoff = payment._seek_for_lines()
        return liquidity, counterpart

    def test_forced_balance_is_kept_outside_the_wizard(self):
        # 100 USD a 40 son 4.000,00 Bs; el balance forzado es 4.000,01.
        payment = self._create_usd_payment(4000.01)
        liquidity, counterpart = self._balances(payment)
        self.assertAlmostEqual(liquidity.balance, 4000.01, places=2)
        self.assertAlmostEqual(counterpart.balance, -4000.01, places=2)
        self.assertAlmostEqual(liquidity.amount_currency, 100.0, places=2)

    def test_forced_balance_is_ignored_for_wizard_payments(self):
        payment = self._create_usd_payment(4000.01, payment_from_wizard=True)
        liquidity, counterpart = self._balances(payment)
        self.assertAlmostEqual(liquidity.balance, 4000.0, places=2)
        self.assertAlmostEqual(counterpart.balance, -4000.0, places=2)
