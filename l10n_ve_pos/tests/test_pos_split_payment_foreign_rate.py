"""Pagos de banco con la tasa cambiada antes del cierre (tarea 83148, H15).

Si el diario del método no está en la moneda alterna, ``l10n_ve_accountant``
valora la línea de liquidez a la tasa de la fecha del asiento (el cierre): con
la tasa cambiada después de la venta, el pago descuadra en alterno contra la
línea por cobrar, que lleva el ``foreign_amount`` cobrado.

En Odoo 19 esto se probaba sobre los pagos de los métodos con
``split_transactions`` (``_create_split_account_payments``). Odoo 20 ya no
tiene ese camino: el cierre crea un ``account.payment`` por método, y las
pruebas lo verifican sobre el cierre completo.

Spec: ``openspec/changes/l10n-ve-pos-split-payment-foreign-rate``.
"""

from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionClosingBase

SALE_RATE = 36.5


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_split_payment_foreign_rate")
class TestPosSplitPaymentForeignRate(TestPosSessionClosingBase):
    def _bank_payment_move(self, amount=58.0, tax_amount=8.0):
        session = self._open_session()
        self._create_paid_order(
            session,
            method=self.bank_method,
            amount=amount,
            tax_amount=tax_amount,
            foreign_rate=SALE_RATE,
            name="OL/H15",
        )
        self._close(session, 0.0)
        move = session.sale_move_ids or session.refund_move_ids
        term_line = move.line_ids.filtered(lambda line: line.display_type == "payment_term")
        counterparts = (
            term_line.matched_debit_ids.debit_move_id
            | term_line.matched_credit_ids.credit_move_id
        ) - term_line
        return session, counterparts.move_id

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
        session, move = self._bank_payment_move()
        # 58 a la tasa de la venta, no a la del cierre (58 × 1 = 58).
        self.assertBalancedInForeign(move, 58.0 * SALE_RATE)

    def test_account_payment_takes_the_rate_of_the_config(self):
        session, move = self._bank_payment_move()
        account_payment = move.origin_payment_id
        self.assertAlmostEqual(
            account_payment.foreign_inverse_rate, session.config_id.foreign_inverse_rate, places=12
        )

    def test_outbound_payment_balanced_in_foreign(self):
        session, move = self._bank_payment_move(amount=-58.0, tax_amount=-8.0)
        self.assertEqual(move.origin_payment_id.payment_type, "outbound")
        self.assertBalancedInForeign(move, 58.0 * SALE_RATE)
