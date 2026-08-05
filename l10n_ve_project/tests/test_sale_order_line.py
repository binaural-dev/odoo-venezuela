# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import L10nVeProjectTestCommon


@tagged("post_install", "-at_install", "l10n_ve_project")
class TestSaleOrderLine(L10nVeProjectTestCommon):
    """Tests for sale.order.line foreign_amount_to_invoice / foreign_amount_invoiced.

    The test product is priced at 100 VEF. With the USD rate at 0.05
    (1 USD = 20 VEF) the foreign price is 5 USD per unit.
    """

    def test_sol_foreign_amount_split_before_invoice(self):
        so, sol = self._create_sale_order(quantity=2.0, price_unit=100.0)
        self.assertTrue(so.state == "sale")
        self.assertAlmostEqual(sol.foreign_subtotal, 10.0, places=2)
        self.assertAlmostEqual(sol.qty_invoiced, 0.0, places=2)
        self.assertAlmostEqual(sol.qty_to_invoice, 2.0, places=2)
        self.assertAlmostEqual(sol.foreign_amount_invoiced, 0.0, places=2)
        self.assertAlmostEqual(sol.foreign_amount_to_invoice, 10.0, places=2)

    def test_sol_foreign_amount_split_after_partial_invoice(self):
        so, sol = self._create_sale_order(quantity=2.0, price_unit=100.0)
        invoice = self._create_customer_invoice(quantity=1.0, price_unit=100.0, sale_lines=sol)
        self._post(invoice)
        self.assertAlmostEqual(sol.qty_invoiced, 1.0, places=2)
        self.assertAlmostEqual(sol.qty_to_invoice, 1.0, places=2)
        self.assertAlmostEqual(sol.foreign_amount_invoiced, 5.0, places=2)
        self.assertAlmostEqual(sol.foreign_amount_to_invoice, 5.0, places=2)

    def test_sol_foreign_amount_split_zero_quantity(self):
        so, sol = self._create_sale_order(quantity=0.0, price_unit=100.0)
        self.assertAlmostEqual(sol.foreign_amount_invoiced, 0.0, places=2)
        self.assertAlmostEqual(sol.foreign_amount_to_invoice, 0.0, places=2)

    def test_sol_foreign_amount_split_full_invoice(self):
        so, sol = self._create_sale_order(quantity=2.0, price_unit=100.0)
        invoice = self._create_customer_invoice(quantity=2.0, price_unit=100.0, sale_lines=sol)
        self._post(invoice)
        self.assertAlmostEqual(sol.qty_invoiced, 2.0, places=2)
        self.assertAlmostEqual(sol.foreign_amount_invoiced, 10.0, places=2)
        self.assertAlmostEqual(sol.foreign_amount_to_invoice, 0.0, places=2)

    def test_sol_foreign_amount_split_after_refund(self):
        """foreign_amount_invoiced must net out credit notes (out_refund),
        as documented in the README."""
        so, sol = self._create_sale_order(quantity=2.0, price_unit=100.0)
        refund = self._create_customer_invoice(
            quantity=1.0, price_unit=100.0, sale_lines=sol, move_type="out_refund"
        )
        self._post(refund)
        self.assertAlmostEqual(sol.foreign_amount_invoiced, -5.0, places=2)

    def test_sol_foreign_amount_split_diverging_rates(self):
        """foreign_amount_invoiced must reflect the invoice's own rate, not
        the sale order's rate, when they differ.

        The order is dated 5 days ago at 1 USD = 25 VEF (rate 0.04), so its
        foreign subtotal is 8.0 USD. The invoice is posted today at the
        common setup rate 1 USD = 20 VEF (rate 0.05), so the real invoiced
        amount is 10.0 USD, not the order's 8.0.
        """
        past_date = fields.Date.today() - timedelta(days=5)
        self.env["res.currency.rate"].create({
            "currency_id": self.usd.id,
            "rate": 0.04,
            "name": past_date,
            "company_id": self.company.id,
        })
        so, sol = self._create_sale_order(quantity=2.0, price_unit=100.0, date_order=past_date)
        self.assertAlmostEqual(sol.foreign_subtotal, 8.0, places=2)

        invoice = self._create_customer_invoice(quantity=2.0, price_unit=100.0, sale_lines=sol)
        self._post(invoice)

        self.assertAlmostEqual(sol.foreign_amount_invoiced, 10.0, places=2)
        self.assertAlmostEqual(sol.foreign_amount_to_invoice, 0.0, places=2)
