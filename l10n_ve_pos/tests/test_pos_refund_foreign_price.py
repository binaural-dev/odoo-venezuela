"""Refund line foreign-price backfill tests (ticket #15106).

Odoo 19 creates the refund order line in the frontend
(``TicketScreen.onDoRefund``) with a direct ``create`` that bypasses the JS
``setUnitPrice`` override — the only place that fills ``foreign_price`` on the
client — so the refund line syncs with ``foreign_price = 0``. That 0 flows into
the credit note through ``pos.order._get_invoice_lines_values`` (which copies
``pos.order.line.foreign_price`` onto the accounting line), leaving the product
lines at 0,00 in the alternate currency and the whole NC unbalanced in USD.

Since #16676 the server also completes any sale line saved without
``foreign_price`` (``pos_sale`` settlement), and a refund whose original is
also at 0 is computed at the original sale's PdV rate.

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
                "foreign_amount_total": 0.0,
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

    def test_sale_line_without_foreign_price_is_filled(self):
        session = self._new_session()

        # Una línea de venta sin alterno se completa con precio x tasa del PdV
        # de la orden (#16676); antes quedaba en 0.
        sale = self._sale_line(self._order_header(session), foreign_price=0.0)

        self.assertAlmostEqual(sale.foreign_price, sale.price_unit * 36.5)

    def test_refund_line_computed_at_original_rate_when_original_has_no_foreign_price(self):
        session = self._new_session()
        sale = self._sale_line(self._order_header(session), foreign_price=0.0)
        # Original dañada (anterior al fix): 0 forzado por SQL.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE pos_order_line SET foreign_price = 0 WHERE id = %s", (sale.id,)
        )
        sale.invalidate_recordset(["foreign_price"])

        # El reembolso se hace a otra tasa: se calcula a la de la venta original.
        refund_line = self._refund_line(
            self._order_header(session, rate=40.0, name="OL/REF-NC"),
            sale,
            foreign_price=0.0,
        )

        self.assertAlmostEqual(refund_line.foreign_price, refund_line.price_unit * 36.5)
