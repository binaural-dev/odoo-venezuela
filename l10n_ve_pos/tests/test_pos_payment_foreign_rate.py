"""Tasa de los pagos del PdV (tarea 83148, H7).

H7: el PdV serializa los pagos anidados en la orden (``deepSerialization`` del
core), sin pasar por ``PosPayment.serializeForORM``, así que
``pos.payment.foreign_rate`` llegaba en 0. El servidor rellena los pagos que
llegan sin tasa (bundles anteriores al fix, órdenes offline): la de la orden, o
la de la orden original si es un reembolso.

Spec: ``openspec/changes/l10n-ve-pos-payment-foreign-rate`` (H7).
"""

from odoo import Command
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase

SALE_RATE = 36.5
ORIGINAL_RATE = 30.0


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_payment_foreign_rate")
class TestPosPaymentForeignRate(TestPosSessionAccountingBase):
    def _new_session(self):
        return self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )

    def _draft_order(self, session, *, rate=SALE_RATE, qty=1.0, refunded_line=None, name="OL/RATE"):
        """Orden en proceso con una línea (``qty`` negativa y ``refunded_line``
        para un reembolso), sin pagos."""
        amount, tax_amount = 116.0 * qty, 16.0 * qty
        line = {
            "name": name,
            "product_id": self.product.id,
            "price_unit": 100.0,
            "qty": qty,
            "price_subtotal": amount - tax_amount,
            "price_subtotal_incl": amount,
            "tax_ids": [Command.set(self.tax.ids)],
            "foreign_price": 100.0 * rate,
        }
        if refunded_line:
            line["refunded_orderline_id"] = refunded_line.id
        return self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": session.id,
                "partner_id": self.company.partner_id.id,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                "foreign_amount_total": amount * rate,
                "foreign_currency_rate": rate,
                "lines": [Command.create(line)],
                "amount_total": amount,
                "amount_tax": tax_amount,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )

    def _add_payment(self, order, *, foreign_rate=0.0, method=None):
        """Pago como lo crea la sincronización del PdV: con ``foreign_amount``
        y la tasa que haya llegado (0 en los bundles anteriores a H7)."""
        order.add_payment(
            {
                "name": "PAY",
                "pos_order_id": order.id,
                "amount": order.amount_total,
                "payment_method_id": (method or self.combined_bank_method).id,
                "payment_date": order.date_order,
                "foreign_amount": order.foreign_amount_total,
                "foreign_rate": foreign_rate,
            }
        )
        return order.payment_ids.filtered(lambda p: not p.is_change)[-1:]

    def _process_payments(self, order, session):
        # amount_return=0: el core no crea vuelto, solo corre el relleno.
        self.env["pos.order"]._process_payment_lines(
            {"amount_return": 0.0}, order, session, False
        )

    # -- H7: relleno de la tasa de los pagos ----------------------------------

    def test_sale_payment_without_rate_gets_order_rate(self):
        session = self._new_session()
        order = self._draft_order(session)
        payment = self._add_payment(order, foreign_rate=0.0)

        self._process_payments(order, session)

        self.assertEqual(payment.foreign_rate, SALE_RATE)

    def test_refund_payment_without_rate_gets_original_rate(self):
        session = self._new_session()
        original = self._draft_order(session, rate=ORIGINAL_RATE, name="OL/ORIG")
        # El reembolso se hace hoy (otra tasa en la orden), pero su foreign_amount
        # va a la tasa de la venta original, y su pago también.
        refund = self._draft_order(
            session, rate=SALE_RATE, qty=-1.0, refunded_line=original.lines, name="OL/NC"
        )
        payment = self._add_payment(refund, foreign_rate=0.0)

        self._process_payments(refund, session)

        self.assertEqual(payment.foreign_rate, ORIGINAL_RATE)

    def test_payment_with_rate_is_kept(self):
        session = self._new_session()
        order = self._draft_order(session)
        payment = self._add_payment(order, foreign_rate=33.0)

        self._process_payments(order, session)

        self.assertEqual(payment.foreign_rate, 33.0)
