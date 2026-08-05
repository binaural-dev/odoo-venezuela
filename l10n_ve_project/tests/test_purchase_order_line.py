# -*- coding: utf-8 -*-

from odoo.tests import tagged

from .common import L10nVeProjectTestCommon


@tagged("post_install", "-at_install", "l10n_ve_project")
class TestPurchaseOrderLine(L10nVeProjectTestCommon):
    """Tests for purchase.order.line foreign_amount_to_bill / foreign_amount_billed.

    The test product is priced at 100 VEF. With the USD rate at 0.05
    (1 USD = 20 VEF) the foreign price is 5 USD per unit.
    """

    def test_pol_foreign_amount_split_before_bill(self):
        po, pol = self._create_purchase_order(quantity=2.0, price_unit=100.0)
        self.assertTrue(po.state == "purchase")
        self.assertAlmostEqual(pol.foreign_subtotal, 10.0, places=2)
        self.assertAlmostEqual(pol.qty_invoiced, 0.0, places=2)
        self.assertAlmostEqual(pol.foreign_amount_billed, 0.0, places=2)
        self.assertAlmostEqual(pol.foreign_amount_to_bill, 10.0, places=2)

    def test_pol_foreign_amount_split_after_partial_bill(self):
        po, pol = self._create_purchase_order(quantity=2.0, price_unit=100.0)
        bill = self._create_bill(quantity=1.0, price_unit=100.0, purchase_line=pol)
        self._post(bill)
        self.assertAlmostEqual(pol.qty_invoiced, 1.0, places=2)
        self.assertAlmostEqual(pol.foreign_amount_billed, 5.0, places=2)
        self.assertAlmostEqual(pol.foreign_amount_to_bill, 5.0, places=2)

    def test_pol_foreign_amount_split_full_bill(self):
        po, pol = self._create_purchase_order(quantity=2.0, price_unit=100.0)
        bill = self._create_bill(quantity=2.0, price_unit=100.0, purchase_line=pol)
        self._post(bill)
        self.assertAlmostEqual(pol.qty_invoiced, 2.0, places=2)
        self.assertAlmostEqual(pol.foreign_amount_billed, 10.0, places=2)
        self.assertAlmostEqual(pol.foreign_amount_to_bill, 0.0, places=2)

    def test_pol_foreign_amount_split_zero_quantity(self):
        po, pol = self._create_purchase_order(quantity=0.0, price_unit=100.0)
        self.assertAlmostEqual(pol.foreign_amount_billed, 0.0, places=2)
        self.assertAlmostEqual(pol.foreign_amount_to_bill, 0.0, places=2)

    def test_pol_foreign_amount_split_qty_fully_invoiced_amount_mismatch(self):
        """foreign_amount_to_bill must reflect the real monetary gap, not 0,
        when the quantity is fully invoiced but the invoiced amount doesn't
        match the order's subtotal (two posted bills at a different price
        than the order)."""
        po, pol = self._create_purchase_order(quantity=4.0, price_unit=100.0)
        bill_1 = self._create_bill(quantity=2.0, price_unit=100.0, purchase_line=pol)
        self._post(bill_1)
        bill_2 = self._create_bill(quantity=2.0, price_unit=120.0, purchase_line=pol)
        self._post(bill_2)
        self.assertEqual(pol.qty_invoiced, pol.product_qty)
        self.assertAlmostEqual(pol.foreign_amount_billed, 22.0, places=2)
        self.assertAlmostEqual(pol.foreign_amount_to_bill, -2.0, places=2)
