# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import TestDonationCommon


@tagged("post_install", "-at_install", "l10n_ve_donation")
class TestDonationSaleOrder(TestDonationCommon):
    """`is_donation` on `sale.order`: the contact is NOT forced to the
    company (the header keeps the real donor/beneficiary), the document is
    an invoice and the warehouse is the donation one of the company."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_partner = cls.company.partner_id
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

    def test_onchange_is_donation_sets_document_and_donation_warehouse(self):
        order = self._create_order()
        order.is_donation = True
        order._onchange_is_donation()
        self.assertEqual(order.document, "invoice")
        self.assertEqual(order.warehouse_id, self.warehouse_donation)

    def test_onchange_is_donation_keeps_the_real_contact(self):
        order = self._create_order()
        order.is_donation = True
        order._onchange_is_donation()
        self.assertEqual(order.partner_id, self.partner)

    def test_changing_the_contact_of_a_donation_is_allowed(self):
        order = self._create_order(partner=self.company_partner, is_donation=True)
        order.partner_id = self.partner
        self.assertEqual(order.partner_id, self.partner)

    def test_onchange_is_donation_requires_a_donation_warehouse(self):
        self.warehouse_donation.is_donation_warehouse = False
        order = self._create_order()
        order.is_donation = True
        with self.assertRaises(ValidationError):
            order._onchange_is_donation()

    def test_onchange_is_donation_off_restores_a_regular_warehouse(self):
        order = self._create_order(is_donation=True)
        order.is_donation = False
        order._onchange_is_donation()
        self.assertFalse(order.warehouse_id.is_donation_warehouse)

    def test_is_donation_cannot_change_on_a_confirmed_order(self):
        order = self._create_order(is_donation=True)
        order.state = "sale"
        with self.assertRaises(ValidationError):
            order.write({"is_donation": False})
        order.write({"is_donation": True})  # same value: allowed

    def test_prepare_invoice_propagates_is_donation(self):
        order = self._create_order(partner=self.partner, is_donation=True)
        invoice_vals = order._prepare_invoice()
        self.assertTrue(invoice_vals.get("is_donation"))
        self.assertEqual(invoice_vals.get("partner_id"), self.partner.id)

    def test_prepare_invoice_regular_order_is_not_a_donation(self):
        order = self._create_order(is_donation=False)
        self.assertFalse(order._prepare_invoice().get("is_donation"))
