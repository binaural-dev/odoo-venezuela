# -*- coding: utf-8 -*-

from odoo.tests import tagged

from .common import L10nVeProjectTestCommon


@tagged("post_install", "-at_install", "l10n_ve_project")
class TestProfitabilityPanel(L10nVeProjectTestCommon):
    """Tests for get_panel_data() foreign currency injection."""

    def test_panel_data_foreign_currency_fields(self):
        panel = self.project.get_panel_data()
        self.assertEqual(panel["currency_id"], self.vef.id)
        self.assertEqual(panel["foreign_currency_id"], self.usd.id)
        self.assertEqual(panel["foreign_currency_symbol"], "$")

    def test_panel_data_profitability_has_foreign_totals(self):
        panel = self.project.get_panel_data()
        profitability = panel["profitability_items"]
        self.assertEqual(profitability["revenues"]["total"]["foreign_to_invoice"], 0.0)
        self.assertEqual(profitability["revenues"]["total"]["foreign_invoiced"], 0.0)
        self.assertEqual(profitability["costs"]["total"]["foreign_to_bill"], 0.0)
        self.assertEqual(profitability["costs"]["total"]["foreign_billed"], 0.0)

    def test_panel_data_with_profitability_data(self):
        po, pol = self._create_purchase_order(quantity=2.0, price_unit=100.0)
        panel = self.project.get_panel_data()
        self.assertEqual(panel["foreign_currency_id"], self.usd.id)
        self.assertEqual(panel["foreign_currency_symbol"], "$")
        costs = panel["profitability_items"]["costs"]["data"]
        purchase_section = next(item for item in costs if item["id"] == "purchase_order")
        self.assertAlmostEqual(purchase_section["foreign_to_bill"], -10.0, places=2)

    def test_get_foreign_currency_symbol(self):
        self.assertEqual(self.project._get_foreign_currency_symbol(), "$")
