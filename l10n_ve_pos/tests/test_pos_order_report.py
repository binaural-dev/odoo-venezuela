"""Foreign-currency (USD) measures of the POS orders analysis report (task #86940)."""

from odoo import Command
from odoo.tests import tagged
from odoo.tools.float_utils import float_compare

from .test_pos_session_accounting_common import TestPosSessionAccountingBase


@tagged("post_install", "-at_install", "l10n_ve_pos", "pos_order_report")
class TestPosOrderReport(TestPosSessionAccountingBase):
    """Company in Bs (VEF) with USD as foreign currency, as the real client."""

    company_currency_name = "VEF"
    foreign_currency_name = "USD"
    # ``foreign_currency_rate`` of the order: dollars per bolivar (40 Bs/$).
    FOREIGN_RATE = 0.025

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.session = cls.env["pos.session"].create(
            {
                "config_id": cls.config.id,
                "user_id": cls.env.ref("base.user_admin").id,
            }
        )

    def _create_order(self, qty, price_unit, tax_amount, refunded_line=None, rate=None):
        """Create an order with a single line priced in Bs.

        No foreign amount is written on the line: the report must derive it
        from the line amounts and the frozen rate of the order, just like the
        POS does. ``rate`` overrides the order's ``foreign_currency_rate``
        (e.g. a refund made on another day).
        """
        rate = self.FOREIGN_RATE if rate is None else rate
        subtotal = qty * price_unit
        total = subtotal + tax_amount
        line_vals = {
            "product_id": self.product.id,
            "qty": qty,
            "price_unit": price_unit,
            "price_subtotal": subtotal,
            "price_subtotal_incl": total,
            "tax_ids": [Command.set(self.tax.ids)],
        }
        if refunded_line:
            line_vals["refunded_orderline_id"] = refunded_line.id
        return self.env["pos.order"].create(
            {
                "company_id": self.company.id,
                "session_id": self.session.id,
                "partner_id": self.company.partner_id.id,
                "pricelist_id": self.company.partner_id.property_product_pricelist.id,
                "foreign_currency_rate": rate,
                "foreign_amount_total": total * rate,
                "amount_total": total,
                "amount_tax": tax_amount,
                "amount_paid": total,
                "amount_return": 0.0,
                "last_order_preparation_change": "{}",
                "lines": [Command.create(line_vals)],
            }
        )

    def _report_line(self, order_line):
        self.env.flush_all()
        return self.env["report.pos.order"].search([("id", "=", order_line.id)])

    def _assert_amount(self, value, expected, label):
        self.assertEqual(
            float_compare(value, expected, precision_digits=2),
            0,
            f"{label}: expected {expected}, got {value}",
        )

    def test_report_foreign_amounts_from_order_rate(self):
        """The report shows the USD subtotal and total of a sale line.

        4,000 Bs untaxed + 640 Bs tax at 40 Bs/$ must report 100 $ untaxed
        and 116 $ total, in the company's foreign currency.
        """
        order = self._create_order(qty=2.0, price_unit=2000.0, tax_amount=640.0)
        report = self._report_line(order.lines)

        self.assertTrue(report, "The order line must appear in report.pos.order")
        self.assertEqual(report.foreign_currency_id, self.company.foreign_currency_id)
        self._assert_amount(report.foreign_untaxed_total, 100.0, "Foreign untaxed total")
        self._assert_amount(report.foreign_total_billed, 116.0, "Foreign total billed")

    def test_report_foreign_amounts_refund_is_negative(self):
        """A refund line subtracts its USD amounts, like ``price_total`` does.

        Grouping a sale of 2 units and the refund of 1 unit must leave half
        of the sale in USD.
        """
        sale = self._create_order(qty=2.0, price_unit=2000.0, tax_amount=640.0)
        refund = self._create_order(
            qty=-1.0, price_unit=2000.0, tax_amount=-320.0, refunded_line=sale.lines
        )
        report = self._report_line(refund.lines)

        self._assert_amount(report.foreign_untaxed_total, -50.0, "Refund foreign untaxed total")
        self._assert_amount(report.foreign_total_billed, -58.0, "Refund foreign total billed")

        [(net_untaxed, net_total)] = self.env["report.pos.order"]._read_group(
            [("order_id", "in", (sale | refund).ids)],
            aggregates=["foreign_untaxed_total:sum", "foreign_total_billed:sum"],
        )
        self._assert_amount(net_untaxed, 50.0, "Net foreign untaxed")
        self._assert_amount(net_total, 58.0, "Net foreign total")

    def test_report_refund_uses_original_sale_rate(self):
        """A refund made at another rate is valued at the original sale's rate.

        The sale of 4,000 Bs + 640 Bs tax is made at 40 Bs/$ (100 $ / 116 $)
        and fully refunded another day at 50 Bs/$. The refund must subtract
        100 $ / 116 $ (not 80 $ / 92.80 $), so the net USD of the pair is 0,
        matching the invoice and its credit note.
        """
        sale = self._create_order(qty=2.0, price_unit=2000.0, tax_amount=640.0)
        refund = self._create_order(
            qty=-2.0,
            price_unit=2000.0,
            tax_amount=-640.0,
            refunded_line=sale.lines,
            rate=0.02,
        )
        report = self._report_line(refund.lines)

        self._assert_amount(report.foreign_untaxed_total, -100.0, "Refund foreign untaxed total")
        self._assert_amount(report.foreign_total_billed, -116.0, "Refund foreign total billed")

        [(net_untaxed, net_total)] = self.env["report.pos.order"]._read_group(
            [("order_id", "in", (sale | refund).ids)],
            aggregates=["foreign_untaxed_total:sum", "foreign_total_billed:sum"],
        )
        self._assert_amount(net_untaxed, 0.0, "Net foreign untaxed")
        self._assert_amount(net_total, 0.0, "Net foreign total")

    def test_report_order_without_rate_reports_zero(self):
        """An order without ``foreign_currency_rate`` reports 0 in USD.

        This is the expected behavior: there is no rate to convert with, and
        the line must still appear with its Bs amounts.
        """
        order = self._create_order(qty=1.0, price_unit=2000.0, tax_amount=320.0, rate=0.0)
        report = self._report_line(order.lines)

        self.assertTrue(report, "The order line must appear in report.pos.order")
        self._assert_amount(report.foreign_untaxed_total, 0.0, "Foreign untaxed total")
        self._assert_amount(report.foreign_total_billed, 0.0, "Foreign total billed")

    def test_report_views_label_measures_with_foreign_currency(self):
        """Pivot and graph views label the USD measures with the currency name."""
        report_model = self.env["report.pos.order"].with_company(self.company)
        for view_type in ("pivot", "graph"):
            arch = report_model.get_view(view_type=view_type)["arch"]
            self.assertIn('string="Subtotal USD"', arch, f"{view_type} subtotal label")
            self.assertIn('string="Total USD"', arch, f"{view_type} total label")
