import re

from lxml import etree

from odoo import Command, fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_sale")
class TestSaleOrderAlternateTotalsBlock(TransactionCase):
    """La orden de venta muestra el segundo bloque de totales: VES si la orden
    esta en otra moneda, moneda de referencia si esta en la de la compania."""

    def setUp(self):
        super().setUp()
        self.company = self.env.company
        self.ves = self.env.ref("base.VEF")
        self.usd = self.env.ref("base.USD")
        self.company.currency_id = self.ves
        self.company.foreign_currency_id = self.usd
        self.env["res.currency.rate"].create({
            "currency_id": self.usd.id, "company_id": self.company.id,
            "name": fields.Date.today(), "rate": 1.0 / 380.0,
        })
        self.partner = self.env["res.partner"].create({"name": "Alt Totals SO Partner"})
        self.product = self.env["product.product"].create({
            "name": "Alt Totals Product", "list_price": 100.0, "taxes_id": [Command.clear()],
        })

    @staticmethod
    def _digits(text):
        return re.sub(r"\D", "", text)

    def _order(self, currency, price_unit):
        pricelist = self.env["product.pricelist"].search([("currency_id", "=", currency.id)], limit=1) or \
            self.env["product.pricelist"].create({"name": f"PL {currency.name}", "currency_id": currency.id})
        return self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "pricelist_id": pricelist.id,
            "order_line": [Command.create({
                "product_id": self.product.id, "product_uom_qty": 1.0,
                "price_unit": price_unit, "tax_ids": [Command.clear()],
            })],
        })

    def test_company_currency_order_exposes_reference_currency_amounts(self):
        order = self._order(self.ves, 3800.0)
        totals = order.tax_totals
        self.assertEqual(totals["currency_id"], self.ves.id)
        self.assertEqual(totals["ves_currency_id"], self.ves.id)
        self.assertEqual(totals["foreign_currency_id"], self.usd.id)
        self.assertAlmostEqual(totals["total_amount_currency"], 3800.0, places=2)
        self.assertAlmostEqual(totals["total_amount_foreign_currency"], 10.0, places=2)
        self.assertAlmostEqual(totals["subtotals"][0]["base_amount_foreign_currency"], 10.0, places=2)

    def test_foreign_currency_order_exposes_company_currency_amounts(self):
        order = self._order(self.usd, 10.0)
        totals = order.tax_totals
        self.assertEqual(totals["currency_id"], self.usd.id)
        self.assertNotEqual(totals["currency_id"], totals["ves_currency_id"])
        self.assertAlmostEqual(totals["total_amount_currency"], 10.0, places=2)
        self.assertIn("380000", self._digits(totals["formatted_total_amount_currency_ves"]))

    def test_form_has_alternate_widget(self):
        arch = etree.fromstring(self.env["sale.order"].get_view(view_type="form")["arch"])
        self.assertTrue(arch.xpath("//group[@name='sale_total']/field[@widget='account-tax-ves-totals-field']"))
        self.assertTrue(arch.xpath("//group[@name='sale_total']/field[@widget='account-tax-totals-field']"))
        self.assertFalse(arch.xpath("//page[@name='foreign_currency']"))
