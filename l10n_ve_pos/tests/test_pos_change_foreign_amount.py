"""Change (vuelto) foreign-currency backfill tests (ticket #15090).

Odoo core creates the change payment line server-side
(``pos.order._process_payment_lines`` -> ``is_change=True``) WITHOUT a
``foreign_amount``/``foreign_rate``. Both the invoice payment moves
(``pos.order._generate_pos_order_invoice``) and the session-close cross moves
(``pos.session``) build the alternate-currency columns
(``foreign_debit``/``foreign_credit``) from ``payment.foreign_amount``, so a
missing value left the change move's foreign columns at 0 and the alternate
currency unbalanced against the invoice.

These tests cover the fix: ``pos.order._amount_to_foreign`` and the backfill
in ``pos.order._process_payment_lines``. ``_amount_to_foreign`` is also what fills the
alternate amount of a change line that reaches the closing without one.

Spec: ``openspec/changes/vuelto-monto-alterno-asiento/specs/l10n_ve_pos/spec.md``
"""

from odoo import Command
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_change_foreign")
class TestPosChangeForeignAmount(TestPosSessionAccountingBase):
    def _new_session(self):
        return self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )

    def _draft_order(self, session, *, rate=36.5, amount=116.0, tax_amount=16.0, name="OL/CHG"):
        """A being-processed (draft) order with one line and the given rate.

        Mirrors ``_create_paid_order`` but without the auto payment nor the
        flip to ``paid`` — ``_process_payment_lines`` runs while the order is
        still being processed, and adding a change line to a ``paid`` order
        would trip ``pos.payment._check_amount``.
        """
        return self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": session.id,
                "partner_id": self.company.partner_id.id,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                "foreign_amount_total": amount,
                "foreign_currency_rate": rate,
                "lines": [
                    Command.create(
                        {
                            "name": name,
                            "product_id": self.product.id,
                            "price_unit": amount - tax_amount,
                            "qty": 1.0,
                            "price_subtotal": amount - tax_amount,
                            "price_subtotal_incl": amount,
                            "tax_ids": [(6, 0, self.tax.ids)],
                            "foreign_price": (amount - tax_amount) * rate,
                        }
                    )
                ],
                "amount_total": amount,
                "amount_tax": tax_amount,
                "amount_paid": 0.0,
                "amount_return": 0.0,
            }
        )

    def _add_change(self, order, *, amount=-16.0, foreign_amount=0.0, foreign_rate=0.0):
        """Add a change line the way core does: is_change, no foreign amount.

        ``pos.order.add_payment`` returns None, so the created payment is
        read back from ``order.payment_ids``.
        """
        order.add_payment(
            {
                "name": "CHANGE",
                "pos_order_id": order.id,
                "amount": amount,
                "payment_method_id": self.combined_cash_method.id,
                "payment_date": order.date_order,
                "is_change": True,
                "foreign_amount": foreign_amount,
                "foreign_rate": foreign_rate,
            }
        )
        return order.payment_ids.filtered(lambda p: p.is_change)[:1]

    def test_amount_to_foreign_multiplies_rounds_and_keeps_sign(self):
        order = self._draft_order(self._new_session(), rate=36.5)
        self.assertEqual(
            order._amount_to_foreign(100.0),
            self.foreign_currency.round(100.0 * 36.5),
        )
        # The change is negative; the sign must be preserved.
        self.assertEqual(
            order._amount_to_foreign(-16.0),
            self.foreign_currency.round(-16.0 * 36.5),
        )

    def test_amount_to_foreign_zero_when_no_rate(self):
        order = self._draft_order(self._new_session(), rate=36.5)
        order.foreign_currency_rate = 0.0
        self.assertEqual(order._amount_to_foreign(100.0), 0.0)

    def _add_regular_payment(self, order, amount=120.0):
        order.add_payment(
            {
                "name": "PAY",
                "pos_order_id": order.id,
                "amount": amount,
                "payment_method_id": self.combined_cash_method.id,
                "payment_date": order.date_order,
                "foreign_amount": amount * 36.5,
            }
        )

    def test_process_payment_lines_backfills_change_foreign_amount(self):
        session = self._new_session()
        order = self._draft_order(session, rate=36.5)
        self._add_regular_payment(order)

        # Odoo 20 creates the change line itself from ``amount_return``.
        self.env["pos.order"]._process_payment_lines(
            {"amount_return": -4.0}, order, session, False
        )

        change = order.payment_ids.filtered(lambda p: p.is_change)
        self.assertEqual(len(change), 1)
        self.assertEqual(
            change.foreign_amount,
            self.foreign_currency.round(-4.0 * 36.5),
        )
        self.assertEqual(change.foreign_rate, order.foreign_currency_rate)

    def test_process_payment_lines_replaces_the_previous_change_line(self):
        session = self._new_session()
        order = self._draft_order(session, rate=36.5)
        self._add_regular_payment(order)
        self._add_change(order, amount=-4.0, foreign_amount=-999.0, foreign_rate=1.0)

        # Odoo 20 removes the change of a previous sync and creates it again:
        # the one that stays is the new one, with the amount valued at the
        # rate of the order.
        self.env["pos.order"]._process_payment_lines(
            {"amount_return": -4.0}, order, session, False
        )

        change = order.payment_ids.filtered(lambda p: p.is_change)
        self.assertEqual(len(change), 1)
        self.assertEqual(
            change.foreign_amount,
            self.foreign_currency.round(-4.0 * 36.5),
        )

    def test_process_payment_lines_ignores_non_change_payment(self):
        session = self._new_session()
        order = self._draft_order(session, rate=36.5)
        order.add_payment(
            {
                "name": "REGULAR",
                "pos_order_id": order.id,
                "amount": 116.0,
                "payment_method_id": self.combined_cash_method.id,
                "payment_date": order.date_order,
                "is_change": False,
                "foreign_amount": 0.0,
            }
        )
        regular = order.payment_ids.filtered(lambda p: not p.is_change)[:1]

        self.env["pos.order"]._process_payment_lines(
            {"amount_return": 0.0}, order, session, False
        )

        # The backfill only targets is_change lines; a regular payment that
        # genuinely came in with 0 is not touched here.
        self.assertFalse(regular.foreign_amount)

    def test_change_is_given_in_the_currency_of_the_register(self):
        """Core gives the change in the currency of the first payment; Odoo 19
        gave it in the currency of the register, and so does l10n_ve_pos."""
        session = self._new_session()
        order = self._draft_order(session, rate=36.5)
        order.add_payment(
            {
                "name": "PAY",
                "pos_order_id": order.id,
                "amount": 120.0,
                "payment_method_id": self.combined_cash_method.id,
                "payment_date": order.date_order,
                "foreign_amount": 120.0 * 36.5,
                "foreign_currency_id": self.payment_currency.id,
                "amount_currency": 120.0 * 36.5,
            }
        )

        self.env["pos.order"]._process_payment_lines(
            {"amount_return": -4.0}, order, session, False
        )

        change = order.payment_ids.filtered(lambda p: p.is_change)
        self.assertEqual(len(change), 1)
        self.assertFalse(change.foreign_currency_id)
        self.assertFalse(change.amount_currency)
        self.assertFalse(change.is_foreign_currency)
