"""Alternate currency measures of the sales analysis for the lines of the POS.

``l10n_ve_sale`` gives ``sale.report`` the foreign subtotal and total of the
sale order lines; ``l10n_ve_pos_sale`` gives the same measures to the lines that
come from the POS (``pos_sale`` adds them to the report), valued at the rate the
order was sold with. Sign of refunds and the multiplier 1 of an order without a
rate are the ones of Odoo 19.
"""

from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_ve_pos.tests.test_pos_session_accounting_common import (
    TestPosSessionAccountingBase,
)

RATE = 36.5
SUBTOTAL = 100.0
TOTAL = 116.0


@tagged("post_install", "-at_install", "l10n_ve_pos_sale")
class TestPosSaleReport(TestPosSessionAccountingBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.session = cls.env["pos.session"].create(
            {"config_id": cls.config.id, "user_id": cls.env.ref("base.user_admin").id}
        )

    def _order(self, rate=RATE, sign=1, refunded_line=None):
        line = {
            "name": "OL/REP",
            "product_id": self.product.id,
            "price_unit": SUBTOTAL,
            "qty": sign * 1.0,
            "price_subtotal": sign * SUBTOTAL,
            "price_subtotal_incl": sign * TOTAL,
            "tax_ids": [Command.set(self.tax.ids)],
            "foreign_price": SUBTOTAL * rate,
        }
        if refunded_line:
            line["refunded_orderline_id"] = refunded_line.id
        order = self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": self.session.id,
                "partner_id": self.company.partner_id.id,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                "foreign_amount_total": sign * TOTAL * rate,
                "foreign_currency_rate": rate,
                "lines": [Command.create(line)],
                "amount_total": sign * TOTAL,
                "amount_tax": sign * 16.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
            }
        )
        order.write({"state": "paid"})
        return order

    def _report(self, order):
        self.env.flush_all()
        return (
            self.env["sale.report"]
            .sudo()
            .with_company(self.company)
            .search([("order_reference", "=", f"pos.order,{order.id}")])
        )

    def test_pos_line_gets_foreign_measures_at_the_rate_of_the_order(self):
        order = self._order()

        report = self._report(order)

        self.assertEqual(len(report), 1)
        self.assertEqual(report.foreign_currency_id, self.company.foreign_currency_id)
        self.assertAlmostEqual(report.foreign_untaxed_total, SUBTOTAL * RATE, places=2)
        self.assertAlmostEqual(report.foreign_total_billed, TOTAL * RATE, places=2)

    def test_refund_line_is_negative(self):
        original = self._order()
        refund = self._order(sign=-1, refunded_line=original.lines)

        report = self._report(refund)

        self.assertAlmostEqual(report.foreign_untaxed_total, -SUBTOTAL * RATE, places=2)
        self.assertAlmostEqual(report.foreign_total_billed, -TOTAL * RATE, places=2)

    def test_order_without_rate_keeps_the_amounts_as_they_are(self):
        order = self._order(rate=0.0)

        report = self._report(order)

        self.assertAlmostEqual(report.foreign_untaxed_total, SUBTOTAL, places=2)
        self.assertAlmostEqual(report.foreign_total_billed, TOTAL, places=2)

    def test_each_order_is_valued_at_its_own_rate(self):
        first = self._order(rate=36.5)
        second = self._order(rate=40.0)

        self.assertAlmostEqual(self._report(first).foreign_total_billed, TOTAL * 36.5, places=2)
        self.assertAlmostEqual(self._report(second).foreign_total_billed, TOTAL * 40.0, places=2)
