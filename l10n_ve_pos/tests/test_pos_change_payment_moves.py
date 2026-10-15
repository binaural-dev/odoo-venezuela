"""Asientos de pago con vuelto (tarea 83148, H12).

El core (``point_of_sale`` ``pos.payment._create_payment_moves``) funde el
vuelto en efectivo con el primer cobro en efectivo de la orden en un solo
asiento de pago por el neto, aunque los métodos sean distintos (el vuelto sale
siempre del primer efectivo de la caja). Al cerrar la sesión, el core concilia
la 1122003 por método: un asiento con pagos de dos métodos deja dos partidas
que netean cero sin conciliar. Además ``l10n_ve_pos`` buscaba el asiento de cada
pago por monto, no encontraba el fundido y no le fijaba tasa ni alterno.

Spec: ``openspec/changes/l10n-ve-pos-change-payment-moves``.
"""

from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_ve_pos.models.pos_payment import PosPayment as VePosPayment

from .test_pos_session_accounting_common import TestPosSessionAccountingBase

RATE = 36.5


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_change_payment_moves")
class TestPosChangePaymentMoves(TestPosSessionAccountingBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        other_cash_journal = cls.env["account.journal"].create(
            {
                "name": "C Other Cash Journal",
                "type": "cash",
                "code": "OCC",
                "company_id": cls.company.id,
                "default_account_id": cls.account_cash.id,
            }
        )
        cls.other_cash_method = cls.env["pos.payment.method"].create(
            {
                "name": "C Other Cash",
                "is_cash_count": True,
                "split_transactions": False,
                "company_id": cls.company.id,
                "journal_id": other_cash_journal.id,
            }
        )
        cls.config.write({"payment_method_ids": [Command.link(cls.other_cash_method.id)]})

    def _payment_moves(self, payments):
        """Asientos de pago de ``l10n_ve_pos``, aunque otro módulo lo
        reimplemente encima: ``l10n_ve_pos_igtf`` reescribe
        ``_create_payment_moves`` sin ``super()`` (un asiento por pago, nunca
        funde el vuelto) y, con él instalado como en el CI, este código no se
        ejecutaría."""
        return VePosPayment._create_payment_moves(payments)

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
                "last_order_preparation_change": "{}",
            }
        )
        return order

    def _invoice(self, order):
        """Factura en borrador enlazada después de los pagos: con ella, el core
        ya no deja crear pagos (``pos.payment._check_amount``)."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "journal_id": self.invoice_journal.id,
                "partner_id": self.company.partner_id.id,
            }
        )
        order.write({"account_move": invoice.id})

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

    def test_change_in_other_cash_method_gets_its_own_move(self):
        order = self._order()
        payment = self._pay(order, self.combined_cash_method, 120.0)
        change = self._pay(order, self.other_cash_method, -4.0, is_change=True)

        self._invoice(order)
        moves = self._payment_moves(order.payment_ids)

        self.assertEqual(len(moves), 2)
        self.assertNotEqual(payment.account_move_id, change.account_move_id)
        self.assertEqual(payment.account_move_id.pos_payment_ids, payment)
        self.assertEqual(change.account_move_id.pos_payment_ids, change)
        self.assertMoveForeign(payment.account_move_id, payment.foreign_amount)
        self.assertMoveForeign(change.account_move_id, change.foreign_amount)

    def test_change_in_same_cash_method_merged_with_net_foreign(self):
        order = self._order()
        payment = self._pay(order, self.combined_cash_method, 120.0)
        change = self._pay(order, self.combined_cash_method, -4.0, is_change=True)

        self._invoice(order)
        moves = self._payment_moves(order.payment_ids)

        self.assertEqual(len(moves), 1)
        self.assertEqual(moves.pos_payment_ids, payment | change)
        self.assertAlmostEqual(moves.amount_total, 116.0)
        self.assertMoveForeign(moves, payment.foreign_amount + change.foreign_amount)

    def test_change_merged_with_the_payment_of_its_method(self):
        order = self._order()
        same_method_payment = self._pay(order, self.other_cash_method, 60.0)
        other_payment = self._pay(order, self.combined_cash_method, 60.0)
        change = self._pay(order, self.other_cash_method, -4.0, is_change=True)

        self._invoice(order)
        # El core funde el vuelto con el primer cobro en efectivo del
        # recordset, sea del método que sea.
        moves = self._payment_moves(other_payment | same_method_payment | change)

        self.assertEqual(len(moves), 2)
        self.assertEqual(
            same_method_payment.account_move_id.pos_payment_ids,
            same_method_payment | change,
        )
        self.assertEqual(other_payment.account_move_id.pos_payment_ids, other_payment)
        self.assertMoveForeign(
            same_method_payment.account_move_id,
            same_method_payment.foreign_amount + change.foreign_amount,
        )
        self.assertMoveForeign(other_payment.account_move_id, other_payment.foreign_amount)

    def test_each_payment_finds_its_move_with_equal_amounts(self):
        order = self._order()
        # Mismo monto local, distinto alterno: emparejar por monto cruzaba
        # los asientos.
        bank = self._pay(order, self.combined_bank_method, 58.0, foreign_amount=58.0 * RATE)
        cash = self._pay(
            order, self.combined_cash_method, 58.0, foreign_amount=58.0 * RATE + 1.0
        )

        self._invoice(order)
        self._payment_moves(order.payment_ids)

        self.assertMoveForeign(bank.account_move_id, bank.foreign_amount)
        self.assertMoveForeign(cash.account_move_id, cash.foreign_amount)

    def test_split_method_change_gets_its_own_move(self):
        # Un método dividido se concilia por pago al cerrar: el vuelto fundido
        # entraría en el grupo del cobro y en el suyo.
        order = self._order()
        payment = self._pay(order, self.split_cash_method, 120.0)
        change = self._pay(order, self.split_cash_method, -4.0, is_change=True)

        self._invoice(order)
        moves = self._payment_moves(order.payment_ids)

        self.assertEqual(len(moves), 2)
        self.assertEqual(payment.account_move_id.pos_payment_ids, payment)
        self.assertEqual(change.account_move_id.pos_payment_ids, change)
        self.assertMoveForeign(payment.account_move_id, payment.foreign_amount)
        self.assertMoveForeign(change.account_move_id, change.foreign_amount)

    def test_changes_of_several_methods_get_their_own_moves(self):
        order = self._order()
        payment = self._pay(order, self.combined_cash_method, 130.0)
        change = self._pay(order, self.combined_cash_method, -10.0, is_change=True)
        other_change = self._pay(order, self.other_cash_method, -4.0, is_change=True)

        self._invoice(order)
        moves = self._payment_moves(order.payment_ids)

        self.assertEqual(len(moves), 3)
        for paid in (payment, change, other_change):
            self.assertEqual(paid.account_move_id.pos_payment_ids, paid)
            self.assertMoveForeign(paid.account_move_id, paid.foreign_amount)

    def test_invoice_reconciled_with_change_in_its_own_move(self):
        order = self._order()
        self._pay(order, self.combined_cash_method, 120.0)
        self._pay(order, self.other_cash_method, -4.0, is_change=True)
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "journal_id": self.invoice_journal.id,
                "partner_id": self.company.partner_id.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "quantity": 1.0,
                            "price_unit": 100.0,
                            "tax_ids": [Command.set(self.tax.ids)],
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        order.write({"account_move": invoice.id})

        moves = self._payment_moves(order.payment_ids)
        self.assertEqual(len(moves), 2)
        order._reconcile_invoice_payments(invoice, moves)

        self.assertAlmostEqual(invoice.amount_total, 116.0)
        self.assertTrue(invoice.currency_id.is_zero(invoice.amount_residual))
