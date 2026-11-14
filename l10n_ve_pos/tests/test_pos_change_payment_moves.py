"""Asientos de pago con vuelto (tarea 83148, H12).

En Odoo 19 el vuelto en efectivo se fundía con el primer cobro en efectivo de
la orden en un solo asiento de pago, aunque los métodos fueran distintos, y
``l10n_ve_pos`` buscaba el asiento de cada pago por monto. En Odoo 20 una caja
tiene un solo método de efectivo y el core agrupa los pagos de la factura por
método: el vuelto va en el mismo asiento que el cobro, por el neto. Estas
pruebas verifican que ese asiento lleve la tasa y el alterno del neto.

Spec: ``openspec/changes/l10n-ve-pos-change-payment-moves``.
"""

from odoo import Command
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase

RATE = 36.5


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_change_payment_moves")
class TestPosChangePaymentMoves(TestPosSessionAccountingBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # La factura y el asiento de diferencial llevan fecha de hoy. A 1 Bs
        # por $: la factura sale en USD y se cobra en VEF, y el core convierte
        # los pagos con esta tasa, como la conversión 1:1 de cuando no había.
        cls._create_rate_of_day(1.0)

    def _payment_moves(self, order):
        """Asientos que liquidan la factura de ``order``: Odoo 20 los crea al
        generar la factura (``_generate_pos_order_invoice``)."""
        invoice = order.with_company(self.company)._generate_pos_order_invoice()
        term_lines = invoice.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )
        counterparts = (
            term_lines.matched_debit_ids.debit_move_id
            | term_lines.matched_credit_ids.credit_move_id
        ) - term_lines
        return invoice, counterparts.move_id

    def _order(self):
        session = self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )
        order = self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": session.id,
                "partner_id": self.company.partner_id.id,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                "foreign_amount_total": 116.0 * RATE,
                "foreign_currency_rate": RATE,
                "lines": [
                    Command.create(
                        {
                            "name": "OL/CHG",
                            "product_id": self.product.id,
                            "price_unit": 100.0,
                            "qty": 1.0,
                            "price_subtotal": 100.0,
                            "price_subtotal_incl": 116.0,
                            "tax_ids": [Command.set(self.tax.ids)],
                            "foreign_price": 100.0 * RATE,
                        }
                    )
                ],
                "amount_total": 116.0,
                "amount_tax": 16.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
            }
        )
        return order

    def _pay(self, order, method, amount, is_change=False, foreign_amount=None):
        order.add_payment(
            {
                "name": "CHANGE" if is_change else "PAY",
                "pos_order_id": order.id,
                "amount": amount,
                "payment_method_id": method.id,
                "payment_date": order.date_order,
                "is_change": is_change,
                "foreign_amount": (
                    order._amount_to_foreign(amount) if foreign_amount is None else foreign_amount
                ),
                "foreign_rate": RATE,
            }
        )
        return order.payment_ids.sorted("id")[-1]

    def assertMoveForeign(self, move, foreign_amount):
        self.assertTrue(move.manually_set_rate)
        self.assertAlmostEqual(move.foreign_inverse_rate, RATE, places=12)
        self.assertEqual(
            sorted(move.line_ids.mapped(lambda l: l.foreign_debit + l.foreign_credit)),
            [abs(foreign_amount), abs(foreign_amount)],
        )

    def test_change_in_same_cash_method_merged_with_net_foreign(self):
        order = self._order()
        payment = self._pay(order, self.combined_cash_method, 120.0)
        change = self._pay(order, self.combined_cash_method, -4.0, is_change=True)

        invoice, moves = self._payment_moves(order)

        self.assertEqual(len(moves), 1)
        self.assertAlmostEqual(moves.amount_total, 116.0)
        self.assertMoveForeign(moves, payment.foreign_amount + change.foreign_amount)

    def test_each_payment_finds_its_move_with_equal_amounts(self):
        order = self._order()
        cash = self._pay(order, self.combined_cash_method, 58.0, foreign_amount=58.0 * 40.0)
        bank = self._pay(order, self.combined_bank_method, 58.0, foreign_amount=58.0 * 30.0)

        invoice, moves = self._payment_moves(order)

        self.assertEqual(len(moves), 2)
        foreign_by_move = sorted(
            move.line_ids[:1].foreign_debit + move.line_ids[:1].foreign_credit
            for move in moves
        )
        self.assertEqual(foreign_by_move, sorted([cash.foreign_amount, bank.foreign_amount]))

    def test_invoice_reconciled_with_change_in_its_own_move(self):
        order = self._order()
        self._pay(order, self.combined_cash_method, 120.0)
        self._pay(order, self.combined_cash_method, -4.0, is_change=True)

        invoice, moves = self._payment_moves(order)

        self.assertAlmostEqual(invoice.amount_total, 116.0)
        self.assertTrue(invoice.currency_id.is_zero(invoice.amount_residual))
