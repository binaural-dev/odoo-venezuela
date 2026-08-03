# -*- coding: utf-8 -*-

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
