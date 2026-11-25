"""IGTF that the original orders of a refund can still give back (tasks 87715 and 87717).

A refund gives back the IGTF of its sale in proportion to what it refunds,
whatever methods pay it. ``pos.order.get_refund_igtf_data`` tells the PoS how
much of the sale is still to refund and how much IGTF is still to give back.
"""

from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_ve_pos.tests.test_pos_session_accounting_common import (
    TestPosSessionAccountingBase,
)

IGTF = 151.11
BASE = 5036.98
FOREIGN_IGTF = 0.16


@tagged("post_install", "-at_install", "l10n_ve_pos_igtf")
class TestPosIgtfRefundShare(TestPosSessionAccountingBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._create_rate_of_day(1.0)
        cls.company.write({"igtf_percentage": 3.0})
        cls.session = cls.env["pos.session"].create(
            {"config_id": cls.config.id, "user_id": cls.env.ref("base.user_admin").id}
        )

    def _order(self, amounts, igtf=0.0, base=0.0, refunded_lines=None, state="paid"):
        refunded_lines = refunded_lines or [None] * len(amounts)
        lines = []
        for amount, refunded_line in zip(amounts, refunded_lines):
            line = {
                "name": "OL/IGTF",
                "product_id": self.product.id,
                "price_unit": abs(amount),
                "qty": 1.0 if amount > 0 else -1.0,
                "price_subtotal": amount,
                "price_subtotal_incl": amount,
                "tax_ids": [Command.clear()],
            }
            if refunded_line:
                line["refunded_orderline_id"] = refunded_line.id
            lines.append(Command.create(line))
        total = sum(amounts)
        order = self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": self.session.id,
                "partner_id": self.company.partner_id.id,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                "lines": lines,
                "amount_total": total,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "igtf_amount": igtf,
                "bi_igtf": base,
                "is_refund": total < 0,
            }
        )
        order.state = state
        return order

    def _pay(self, order, amount, igtf=0.0, foreign_igtf=0.0):
        order.add_payment(
            {
                "name": "PAY",
                "pos_order_id": order.id,
                "amount": amount,
                "payment_method_id": self.combined_bank_method.id,
                "payment_date": order.date_order,
                "include_igtf": bool(igtf),
                "igtf_amount": igtf,
                "foreign_igtf_amount": foreign_igtf,
            }
        )

    def _sale(self):
        """The sale of task 87715: 10.000 Bs, of which 5.036,98 paid in euros
        (IGTF 151,11) and the rest, with that IGTF, in bolivares."""
        sale = self._order([6000.0, 4000.0], igtf=IGTF, base=BASE)
        self._pay(sale, BASE, igtf=IGTF, foreign_igtf=FOREIGN_IGTF)
        self._pay(sale, 10000.0 - BASE + IGTF)
        return sale

    def _remaining(self, order):
        (data,) = self.env["pos.order"].get_refund_igtf_data([order.id])
        return data

    def test_sale_without_refunds_gives_back_what_it_charged(self):
        sale = self._sale()

        self.assertEqual(
            self._remaining(sale),
            {
                "id": sale.id,
                "amount_total": 10000.0,
                "igtf_amount": IGTF,
                "bi_igtf": BASE,
                "foreign_igtf_amount": FOREIGN_IGTF,
            },
        )

    def test_partial_refund_leaves_the_rest_of_the_igtf(self):
        sale = self._sale()
        refund = self._order(
            [-4000.0], igtf=-60.44, base=-2014.79, refunded_lines=sale.lines[1:]
        )
        self._pay(refund, -4060.44, igtf=-60.44, foreign_igtf=-0.06)

        remaining = self._remaining(sale)

        self.assertAlmostEqual(remaining["amount_total"], 6000.0)
        self.assertAlmostEqual(remaining["igtf_amount"], IGTF - 60.44)
        self.assertAlmostEqual(remaining["bi_igtf"], BASE - 2014.79)
        self.assertAlmostEqual(remaining["foreign_igtf_amount"], FOREIGN_IGTF - 0.06)

    def test_refund_in_progress_is_not_counted(self):
        sale = self._sale()
        self._order([-4000.0], igtf=-60.44, base=-2014.79, refunded_lines=sale.lines[1:], state="draft")

        self.assertAlmostEqual(self._remaining(sale)["igtf_amount"], IGTF)

    def test_refund_of_two_orders_counts_its_lines_of_each(self):
        sale = self._sale()
        other = self._order([1000.0], igtf=30.0, base=1000.0)
        self._pay(other, 1030.0, igtf=30.0, foreign_igtf=0.03)
        refund = self._order(
            [-4000.0, -1000.0],
            igtf=-90.44,
            base=-3014.79,
            refunded_lines=[sale.lines[1], other.lines],
        )
        self._pay(refund, -5090.44, igtf=-90.44, foreign_igtf=-0.09)

        self.assertAlmostEqual(self._remaining(sale)["amount_total"], 6000.0)
        self.assertAlmostEqual(self._remaining(sale)["igtf_amount"], IGTF - 90.44 * 0.8, delta=0.005)
        self.assertAlmostEqual(self._remaining(other)["amount_total"], 0.0)
        self.assertAlmostEqual(self._remaining(other)["igtf_amount"], 30.0 - 90.44 * 0.2, delta=0.005)

    def test_whole_refund_leaves_nothing_to_give_back(self):
        sale = self._sale()
        refund = self._order(
            [-6000.0, -4000.0], igtf=-IGTF, base=-BASE, refunded_lines=sale.lines
        )
        self._pay(refund, -10000.0 + BASE - IGTF)
        self._pay(refund, -BASE, igtf=-IGTF, foreign_igtf=-FOREIGN_IGTF)

        remaining = self._remaining(sale)

        self.assertEqual(remaining["amount_total"], 0.0)
        self.assertEqual(remaining["igtf_amount"], 0.0)
        self.assertEqual(remaining["bi_igtf"], 0.0)
        self.assertEqual(remaining["foreign_igtf_amount"], 0.0)

    def test_sale_without_igtf_gives_back_none(self):
        sale = self._order([1000.0])
        self._pay(sale, 1000.0)

        remaining = self._remaining(sale)

        self.assertAlmostEqual(remaining["amount_total"], 1000.0)
        self.assertEqual(remaining["igtf_amount"], 0.0)
        self.assertEqual(remaining["foreign_igtf_amount"], 0.0)
