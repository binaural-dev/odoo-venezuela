# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError
from odoo import Command


@tagged("post_install", "-at_install", "l10n_ve_donation")
class TestDonationSaleOrder(TransactionCase):
    """Coverage for the `is_donation` onchanges/constraint that
    `l10n_ve_donation` adds to `sale.order`."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company_partner = cls.company.partner_id
        cls.partner = cls.env["res.partner"].create({"name": "Donation SO Test Partner"})

        # `l10n_ve_accountant`'s tax-totals computation needs a foreign
        # currency configured on the company to resolve `currency_id` to a
        # singleton -- without it, any sale order line write triggers a
        # dual-currency compute that raises on an empty recordset.
        currency_usd = cls.env.ref("base.USD")
        currency_usd.active = True
        currency_vef = cls.env.ref("base.VEF")
        currency_vef.active = True
        cls.company.write({
            "currency_id": currency_vef.id,
            "foreign_currency_id": currency_usd.id,
        })

        # `l10n_ve_accountant` requires every product to resolve exactly one
        # sale/purchase tax, either explicitly or via the company's default
        # fiscal configuration -- set the latter so products created below
        # (with no taxes_id) don't raise a fiscal-inconsistency UserError.
        # `tax_group_id` has no usable default in a minimal database (no
        # fiscal localization data loaded) -- pass one explicitly to avoid a
        # NOT NULL violation.
        if not cls.company.account_sale_tax_id or not cls.company.account_purchase_tax_id:
            country_ve = cls.env.ref("base.ve")
            tax_group = cls.env["account.tax.group"].create({
                "name": "Donation SO Test Tax Group",
                "country_id": country_ve.id,
            })
        if not cls.company.account_sale_tax_id:
            cls.company.account_sale_tax_id = cls.env["account.tax"].create({
                "name": "Donation SO Test Sale Tax",
                "amount": 16,
                "type_tax_use": "sale",
                "company_id": cls.company.id,
                "tax_group_id": tax_group.id,
                "country_id": country_ve.id,
            })
        if not cls.company.account_purchase_tax_id:
            cls.company.account_purchase_tax_id = cls.env["account.tax"].create({
                "name": "Donation SO Test Purchase Tax",
                "amount": 16,
                "type_tax_use": "purchase",
                "company_id": cls.company.id,
                "tax_group_id": tax_group.id,
                "country_id": country_ve.id,
            })

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
