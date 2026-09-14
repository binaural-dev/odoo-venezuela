"""Refund line foreign-price backfill tests (ticket #15106).

Odoo 19 creates the refund order line in the frontend
(``TicketScreen.onDoRefund``) with a direct ``create`` that bypasses the JS
``setUnitPrice`` override — the only place that fills ``foreign_price`` on the
client — so the refund line syncs with ``foreign_price = 0``. That 0 flows into
the credit note through ``pos.order._get_invoice_lines_values`` (which copies
``pos.order.line.foreign_price`` onto the accounting line), leaving the product
lines at 0,00 in the alternate currency and the whole NC unbalanced in USD.

These tests cover the fix: ``pos.order.line.create`` backfills ``foreign_price``
on a refund line from the line being refunded (``refunded_orderline_id``), so the
credit note reverses the SAME frozen USD unit price as the original sale (the
sale-day rate, not the refund-day rate).

Spec: ``openspec/changes/reembolso-precio-foraneo-linea/specs/l10n_ve_pos/spec.md``
"""

from odoo import Command
from odoo.tests import tagged

from .test_pos_session_accounting_common import TestPosSessionAccountingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_refund_foreign")
class TestPosRefundForeignPrice(TestPosSessionAccountingBase):
    def _new_session(self):
        return self.env["pos.session"].create(
            {
                "config_id": self.config.id,
                "user_id": self.env.ref("base.user_admin").id,
            }
        )

    def _order_header(self, session, *, rate=36.5, name="OL/REF"):
        return self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": session.id,
                "partner_id": self.company.partner_id.id,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                "foreign_currency_rate": rate,
                "amount_total": 0.0,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
            }
        )

    def _sale_line(self, order, *, foreign_price, amount=116.0, tax_amount=16.0):
        return self.env["pos.order.line"].create(
            {
                "order_id": order.id,
                "name": "SALE",
                "product_id": self.product.id,
                "price_unit": amount - tax_amount,
                "qty": 1.0,
                "price_subtotal": amount - tax_amount,
                "price_subtotal_incl": amount,
                "tax_ids": [Command.set(self.tax.ids)],
                "foreign_price": foreign_price,
            }
        )

    def _refund_line(self, order, original_line, *, foreign_price=0.0):
        """A refund line the way core builds it: negative qty, linked to the
        original line, and ``foreign_price`` NOT set (arrives as 0)."""
        return self.env["pos.order.line"].create(
            {
                "order_id": order.id,
                "name": "REFUND",
                "product_id": self.product.id,
                "price_unit": original_line.price_unit,
                "qty": -1.0,
                "price_subtotal": -original_line.price_subtotal,
                "price_subtotal_incl": -original_line.price_subtotal_incl,
                "tax_ids": [Command.set(self.tax.ids)],
                "refunded_orderline_id": original_line.id,
                "foreign_price": foreign_price,
            }
        )

    def test_refund_line_backfills_foreign_price_from_original(self):
        session = self._new_session()
        sale = self._sale_line(self._order_header(session), foreign_price=3.45)

        refund_line = self._refund_line(
            self._order_header(session, name="OL/REF-NC"), sale, foreign_price=0.0
        )

        # The refund line arrived with foreign_price 0; it must be repriced to
        # the original's frozen USD unit price so the NC reverses 1:1.
        self.assertEqual(refund_line.foreign_price, 3.45)

    def test_refund_line_keeps_existing_foreign_price(self):
        session = self._new_session()
        sale = self._sale_line(self._order_header(session), foreign_price=3.45)

        # A refund line that already carries a foreign price (e.g. injected by
        # the backend refund via ``_prepare_refund_data``) must be left as is.
        refund_line = self._refund_line(
            self._order_header(session, name="OL/REF-NC"), sale, foreign_price=2.0
        )

        self.assertEqual(refund_line.foreign_price, 2.0)

    def test_non_refund_line_foreign_price_untouched(self):
        session = self._new_session()

        # A regular sale line (no refunded_orderline_id) is never touched by the
        # backfill: a legitimately-zero foreign price stays zero.
        sale = self._sale_line(self._order_header(session), foreign_price=0.0)

        self.assertEqual(sale.foreign_price, 0.0)

    def test_refund_line_no_backfill_when_original_has_no_foreign_price(self):
        session = self._new_session()
        sale = self._sale_line(self._order_header(session), foreign_price=0.0)

        refund_line = self._refund_line(
            self._order_header(session, name="OL/REF-NC"), sale, foreign_price=0.0
        )

        self.assertEqual(refund_line.foreign_price, 0.0)
