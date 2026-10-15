"""Foreign amounts keep the sign of the local ones (task 83148, H1).

In Odoo 19 a refund line's ``priceIncl`` is the line total times
``order.orderSign`` (a positive magnitude, for display), while
``order.totalDue`` stays negative. The POS summed those magnitudes into the
refund's foreign total and derived a NEGATIVE conversion ratio from it, so
refunds reached the server with ``foreign_amount`` and
``foreign_amount_total`` positive next to a negative ``amount``. The session
close then expected the refund as cash coming IN (false shortage, inflated
cross moves) and crashed on ``amount_currency_balance_sign`` when the net of
a foreign cash method was a refund.

The frontend is fixed at the source (``pos_order.js``); these tests cover the
server guard in ``pos.order._process_saved_order``, which keeps the
magnitude the POS sent but forces the sign of the local amount, so POS
clients still running the old cached bundle (or any other channel) cannot
store the inconsistent sign.
"""

from odoo import Command
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_refund_foreign_sign")
class TestPosRefundForeignSign(TestPosSessionAccountingBase):
    def _new_session(self):
        return self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )

    def _draft_order(self, session, *, amount, foreign_amount_total, rate=36.5):
        """A being-processed (draft) order; ``amount`` < 0 makes it a refund."""
        qty = 1.0 if amount > 0 else -1.0
        return self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": session.id,
                "partner_id": self.company.partner_id.id,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                # As ``pos.order.refund`` does: l10n_ve_pos only allows a
                # negative quantity on refund orders.
                "is_refund": amount < 0,
                "foreign_amount_total": foreign_amount_total,
                "foreign_currency_rate": rate,
                "lines": [
                    Command.create(
                        {
                            "name": "OL/SIGN",
                            "product_id": self.product.id,
                            "price_unit": amount * qty,
                            "qty": qty,
                            "price_subtotal": amount,
                            "price_subtotal_incl": amount,
                        }
                    )
                ],
                "amount_total": amount,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )

    def _add_payment(self, order, *, amount, foreign_amount):
        order.add_payment(
            {
                "name": "PAY",
                "pos_order_id": order.id,
                "amount": amount,
                "payment_method_id": self.combined_cash_method.id,
                "payment_date": order.date_order,
                "foreign_amount": foreign_amount,
            }
        )
        return order.payment_ids[-1:]

    def _process(self, order, session):
        # draft=True: runs the guard without marking the order paid nor
        # invoicing it, which these bare fixtures do not support.
        order._process_saved_order(True)

    def test_refund_foreign_amounts_take_the_local_sign(self):
        session = self._new_session()
        order = self._draft_order(session, amount=-9318.74, foreign_amount_total=11.6)
        payment = self._add_payment(order, amount=-9318.74, foreign_amount=11.6)

        self._process(order, session)

        self.assertEqual(payment.foreign_amount, -11.6)
        self.assertEqual(order.foreign_amount_total, -11.6)

    def test_consistent_refund_is_left_untouched(self):
        session = self._new_session()
        order = self._draft_order(session, amount=-9318.74, foreign_amount_total=-11.6)
        payment = self._add_payment(order, amount=-9318.74, foreign_amount=-11.6)

        self._process(order, session)

        self.assertEqual(payment.foreign_amount, -11.6)
        self.assertEqual(order.foreign_amount_total, -11.6)

    def test_sale_is_left_untouched(self):
        session = self._new_session()
        order = self._draft_order(session, amount=18637.49, foreign_amount_total=23.2)
        payment = self._add_payment(order, amount=18637.49, foreign_amount=23.2)

        self._process(order, session)

        self.assertEqual(payment.foreign_amount, 23.2)
        self.assertEqual(order.foreign_amount_total, 23.2)

    def test_zero_foreign_amount_is_left_untouched(self):
        """A local-method payment without foreign amount keeps its 0: the
        guard only fixes a sign, it never invents an amount."""
        session = self._new_session()
        order = self._draft_order(session, amount=-9318.74, foreign_amount_total=-11.6)
        payment = self._add_payment(order, amount=-9318.74, foreign_amount=0.0)

        self._process(order, session)

        self.assertFalse(payment.foreign_amount)
