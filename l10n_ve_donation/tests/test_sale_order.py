# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo.exceptions import ValidationError
from odoo import Command

from odoo.addons.l10n_ve_stock_account.tests.common import StockAccountTestCommon


@tagged("post_install", "-at_install", "l10n_ve_donation")
class TestDonationSaleOrder(StockAccountTestCommon):
    """Coverage for the `is_donation` onchanges/constraint that
    `l10n_ve_donation` adds to `sale.order`."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_partner = cls.company.partner_id
        cls.partner = cls.env["res.partner"].create({"name": "Donation SO Test Partner"})

        cls.product = cls.env["product.product"].create({
            "name": "Donation SO Coverage Product",
            "type": "consu",
            "lst_price": 100.0,
        })

    def _create_order(self, partner=None, is_donation=False):
        return self.env["sale.order"].create({
            "partner_id": (partner or self.partner).id,
            "is_donation": is_donation,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 100.0,
            })],
        })

    def test_onchange_is_donation_sets_company_partner_and_document(self):
        order = self._create_order()
        order.is_donation = True
        order._onchange_is_donation()
        self.assertEqual(order.partner_id, order.company_id.partner_id)
        self.assertEqual(order.document, "invoice")

    def test_onchange_partner_id_donation_sets_document(self):
        order = self._create_order(partner=self.company_partner, is_donation=True)
        order.partner_id = self.company_partner
        order._onchange_partner_id_donation()
        self.assertEqual(order.document, "invoice")

    def test_onchange_partner_id_donation_raises_for_other_partner(self):
        order = self._create_order(partner=self.company_partner, is_donation=True)
        order.partner_id = self.partner
        with self.assertRaises(ValidationError):
            order._onchange_partner_id_donation()

    def test_prepare_invoice_propagates_is_donation(self):
        order = self._create_order(partner=self.company_partner, is_donation=True)
        invoice_vals = order._prepare_invoice()
        self.assertTrue(invoice_vals.get("is_donation"))
