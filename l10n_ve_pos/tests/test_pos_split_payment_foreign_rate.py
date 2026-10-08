"""Pagos split de banco con la tasa cambiada antes del cierre (tarea 83148, H15).

El core de Odoo 19 crea los ``account.payment`` de los métodos con
``split_transactions`` en lote (``_create_bank_payment_moves`` llama a
``_create_split_account_payments``) y no pasa por
``_create_split_account_payment``. Si el diario del método no está en la
moneda alterna, ``l10n_ve_accountant`` valora la línea de liquidez a la tasa
de la fecha del asiento (el cierre): con la tasa cambiada después de la venta,
el pago descuadra en alterno contra la línea por cobrar, que lleva el
``foreign_amount`` cobrado.

Spec: ``openspec/changes/l10n-ve-pos-split-payment-foreign-rate``.
"""

from odoo import Command, fields
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase

SALE_RATE = 36.5
CLOSING_RATE = 40.0


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_split_payment_foreign_rate")
class TestPosSplitPaymentForeignRate(TestPosSessionAccountingBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Como el banco en Bs de producción: sin moneda propia, el pago va en
        # la moneda de la compañía y su alterno no sale de ``amount_currency``.
        company_bank_journal = cls.env["account.journal"].create(
            {
                "name": "C Company Bank",
                "type": "bank",
                "code": "CCBK",
                "company_id": cls.company.id,
                "default_account_id": cls.account_bank.id,
                "inbound_payment_method_line_ids": [
                    Command.create(
                        {
                            "payment_method_id": cls.env.ref("account.account_payment_method_manual_in").id,
                            "payment_account_id": cls.account_bank.id,
                        }
                    )
                ],
                "outbound_payment_method_line_ids": [
                    Command.create(
                        {
                            "payment_method_id": cls.env.ref("account.account_payment_method_manual_out").id,
                            "payment_account_id": cls.account_bank.id,
                        }
                    )
                ],
            }
        )
        cls.company_split_bank_method = cls.env["pos.payment.method"].create(
            {
                "name": "C Company Split Bank",
                "is_cash_count": False,
                "split_transactions": True,
                "company_id": cls.company.id,
                "journal_id": company_bank_journal.id,
                "outstanding_account_id": cls.account_bank.id,
            }
        )
        cls.config.write(
            {"payment_method_ids": [Command.link(cls.company_split_bank_method.id)]}
        )
        # Tasa del día del cierre, distinta de la de la venta.
        cls.env["res.currency.rate"].create(
            {
                "name": fields.Date.today(),
                "currency_id": cls.foreign_currency.id,
                "company_id": cls.company.id,
                "rate": CLOSING_RATE,
            }
        )

    def _split_payment_move(self, sign=1):
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )
        order = self._create_paid_order(
            session,
            method=self.company_split_bank_method,
            amount=58.0,
            tax_amount=8.0,
            foreign_rate=SALE_RATE,
            name="OL/H15",
        )
        payment = order.payment_ids.with_company(self.company)
        amounts = {
            "amount": sign * payment.amount,
            "amount_converted": sign * payment.amount,
        }
        # El cierre llega aquí desde ``_create_bank_payment_moves`` del core,
        # con todos los pagos split de la sesión.
        payment_to_line = session.with_company(
            self.company
        )._create_split_account_payments([(payment, amounts)])
        return payment, payment_to_line[payment].move_id

    def assertBalancedInForeign(self, move, foreign_amount):
        self.assertEqual(len(move.line_ids), 2)
        for line in move.line_ids:
            self.assertAlmostEqual(line.foreign_debit + line.foreign_credit, foreign_amount, places=2)
            self.assertTrue(line.not_foreign_recalculate)
        self.assertAlmostEqual(
            sum(move.line_ids.mapped("foreign_debit")),
            sum(move.line_ids.mapped("foreign_credit")),
            places=2,
        )
        self.assertAlmostEqual(sum(move.line_ids.mapped("foreign_balance")), 0.0, places=2)

    def test_liquidity_line_keeps_the_charged_foreign_amount(self):
        payment, move = self._split_payment_move()
        # 58 a la tasa de la venta, no a la del cierre (58 × 40 = 2.320).
        self.assertAlmostEqual(payment.foreign_amount, 58.0 * SALE_RATE, places=2)
        self.assertBalancedInForeign(move, 58.0 * SALE_RATE)

    def test_account_payment_takes_the_rate_of_the_payment(self):
        payment, move = self._split_payment_move()
        account_payment = move.origin_payment_id
        self.assertAlmostEqual(account_payment.foreign_inverse_rate, SALE_RATE, places=12)
        self.assertAlmostEqual(move.foreign_inverse_rate, SALE_RATE, places=12)
        self.assertTrue(move.manually_set_rate)

    def test_each_payment_of_the_batch_keeps_its_rate(self):
        """Varios pagos en un mismo lote: cada asiento lleva la tasa y el
        alterno de su propio cobro."""
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )
        payments = self.env["pos.payment"]
        for rate, name in ((SALE_RATE, "OL/H15/A"), (38.0, "OL/H15/B")):
            order = self._create_paid_order(
                session,
                method=self.company_split_bank_method,
                amount=58.0,
                tax_amount=8.0,
                foreign_rate=rate,
                name=name,
            )
            payments |= order.payment_ids
        payments = payments.with_company(self.company)
        payment_to_line = session.with_company(self.company)._create_split_account_payments(
            [(p, {"amount": p.amount, "amount_converted": p.amount}) for p in payments]
        )
        for payment, rate in zip(payments, (SALE_RATE, 38.0)):
            move = payment_to_line[payment].move_id
            self.assertBalancedInForeign(move, 58.0 * rate)
            self.assertAlmostEqual(move.origin_payment_id.foreign_inverse_rate, rate, places=12)
        self.assertEqual(len(payments.mapped(lambda p: payment_to_line[p].move_id)), 2)

    def test_outbound_payment_balanced_in_foreign(self):
        payment, move = self._split_payment_move(sign=-1)
        self.assertEqual(move.origin_payment_id.payment_type, "outbound")
        self.assertBalancedInForeign(move, 58.0 * SALE_RATE)

    def test_singular_method_goes_through_the_batch(self):
        """El ``_create_split_account_payment`` del core delega en el lote:
        quien lo llame sigue recibiendo la línea por cobrar con el alterno."""
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )
        order = self._create_paid_order(
            session,
            method=self.company_split_bank_method,
            amount=58.0,
            tax_amount=8.0,
            foreign_rate=SALE_RATE,
            name="OL/H15/1",
        )
        payment = order.payment_ids.with_company(self.company)
        receivable_line = session.with_company(self.company)._create_split_account_payment(
            payment, {"amount": payment.amount, "amount_converted": payment.amount}
        )
        self.assertEqual(receivable_line._name, "account.move.line")
        self.assertBalancedInForeign(receivable_line.move_id, 58.0 * SALE_RATE)
