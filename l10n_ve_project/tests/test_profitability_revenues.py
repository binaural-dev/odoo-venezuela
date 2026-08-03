# -*- coding: utf-8 -*-

from odoo.tests import tagged

from .common import L10nVeProjectTestCommon


@tagged("post_install", "-at_install", "l10n_ve_project")
class TestProfitabilityRevenues(L10nVeProjectTestCommon):
    """Tests for the foreign amounts of the project profitability revenues.

    Product price 100 VEF, USD rate 0.05 (1 USD = 20 VEF): a full SO line of
    2 units has a foreign subtotal of 10 USD. A revenue of 200 VEF is 10 USD.
    """

    @staticmethod
    def _section(items, key, section_id):
        return next(item for item in items[key]["data"] if item["id"] == section_id)

    def test_revenues_from_sol_before_invoice(self):
        so, sol = self._create_sale_order(quantity=2.0, price_unit=100.0)
        self.project.sale_line_id = sol.id
        items = self.project._get_profitability_items(False)
        section = self._section(items, "revenues", "service_revenues")
        self.assertAlmostEqual(section["to_invoice"], 200.0, places=2)
        self.assertAlmostEqual(section["invoiced"], 0.0, places=2)
        self.assertAlmostEqual(section["foreign_to_invoice"], 10.0, places=2)
        self.assertAlmostEqual(section["foreign_invoiced"], 0.0, places=2)
        self.assertAlmostEqual(items["revenues"]["total"]["foreign_to_invoice"], 10.0, places=2)
        self.assertAlmostEqual(items["revenues"]["total"]["foreign_invoiced"], 0.0, places=2)

    def test_revenues_from_sol_after_partial_invoice(self):
        so, sol = self._create_sale_order(quantity=2.0, price_unit=100.0)
        invoice = self._create_customer_invoice(quantity=1.0, price_unit=100.0, sale_lines=sol)
        self._post(invoice)
        self.project.sale_line_id = sol.id
        items = self.project._get_profitability_items(False)
        section = self._section(items, "revenues", "service_revenues")
        self.assertAlmostEqual(section["to_invoice"], 100.0, places=2)
        self.assertAlmostEqual(section["invoiced"], 100.0, places=2)
        self.assertAlmostEqual(section["foreign_to_invoice"], 5.0, places=2)
        self.assertAlmostEqual(section["foreign_invoiced"], 5.0, places=2)
        self.assertAlmostEqual(items["revenues"]["total"]["foreign_to_invoice"], 5.0, places=2)
        self.assertAlmostEqual(items["revenues"]["total"]["foreign_invoiced"], 5.0, places=2)

    def test_revenues_from_invoice_without_sol_draft(self):
        invoice = self._create_customer_invoice(quantity=1.0, price_unit=200.0)
        self.assertEqual(invoice.state, "draft")
        items = self.project._get_profitability_items(False)
        section = self._section(items, "revenues", "other_invoice_revenues")
        self.assertAlmostEqual(section["to_invoice"], 200.0, places=2)
        self.assertAlmostEqual(section["invoiced"], 0.0, places=2)
        self.assertAlmostEqual(section["foreign_to_invoice"], 10.0, places=2)
        self.assertAlmostEqual(section["foreign_invoiced"], 0.0, places=2)

    def test_revenues_from_invoice_without_sol_posted(self):
        invoice = self._create_customer_invoice(quantity=1.0, price_unit=200.0)
        self._post(invoice)
        items = self.project._get_profitability_items(False)
        section = self._section(items, "revenues", "other_invoice_revenues")
        self.assertAlmostEqual(section["to_invoice"], 0.0, places=2)
        self.assertAlmostEqual(section["invoiced"], 200.0, places=2)
        self.assertAlmostEqual(section["foreign_to_invoice"], 0.0, places=2)
        self.assertAlmostEqual(section["foreign_invoiced"], 10.0, places=2)
        self.assertAlmostEqual(items["revenues"]["total"]["foreign_invoiced"], 10.0, places=2)

    def test_foreign_totals_sum_of_sections(self):
        so, sol = self._create_sale_order(quantity=2.0, price_unit=100.0)
        invoice = self._create_customer_invoice(quantity=1.0, price_unit=100.0, sale_lines=sol)
        self._post(invoice)
        other_invoice = self._create_customer_invoice(quantity=1.0, price_unit=200.0)
        self._post(other_invoice)
        self.project.sale_line_id = sol.id
        items = self.project._get_profitability_items(False)
        total_foreign_invoiced = sum(
            section.get("foreign_invoiced", 0.0) for section in items["revenues"]["data"]
        )
        self.assertAlmostEqual(
            items["revenues"]["total"]["foreign_invoiced"], total_foreign_invoiced, places=2
        )
        self.assertAlmostEqual(
            items["revenues"]["total"]["foreign_to_invoice"],
            sum(section.get("foreign_to_invoice", 0.0) for section in items["revenues"]["data"]),
            places=2,
        )

    def test_revenues_from_downpayment(self):
        so, sol = self._create_sale_order(quantity=2.0, price_unit=100.0)
        dp_sol = self.env["sale.order.line"].with_context(tracking_disable=True).create({
            "order_id": so.id,
            "product_id": self.product.id,
            "product_uom_qty": 0.0,
            "price_unit": 100.0,
            "is_downpayment": True,
        })
        invoice = self._create_customer_invoice(quantity=1.0, price_unit=100.0, sale_lines=dp_sol)
        self._post(invoice)
        self.project.sale_line_id = sol.id
        items = self.project._get_profitability_items()
        section = self._section(items, "revenues", "downpayments")
        self.assertAlmostEqual(section["invoiced"], 100.0, places=2)
        self.assertAlmostEqual(section["to_invoice"], -100.0, places=2)
        self.assertAlmostEqual(section["foreign_invoiced"], 5.0, places=2)
        self.assertAlmostEqual(section["foreign_to_invoice"], -5.0, places=2)
        self.assertIn("action", section)

    def test_revenues_materials_section_with_action(self):
        so, sol = self._create_sale_order(quantity=2.0, price_unit=100.0, product=self.product_consu)
        self.project.sale_line_id = sol.id
        items = self.project._get_profitability_items()
        section = self._section(items, "revenues", "materials")
        self.assertAlmostEqual(section["to_invoice"], 200.0, places=2)
        self.assertAlmostEqual(section["invoiced"], 0.0, places=2)
        self.assertAlmostEqual(section["foreign_to_invoice"], 10.0, places=2)
        self.assertAlmostEqual(section["foreign_invoiced"], 0.0, places=2)
        self.assertIn("action", section)

    def test_other_invoice_revenues_with_action(self):
        invoice = self._create_customer_invoice(quantity=1.0, price_unit=200.0)
        self._post(invoice)
        items = self.project._get_profitability_items()
        section = self._section(items, "revenues", "other_invoice_revenues")
        self.assertAlmostEqual(section["invoiced"], 200.0, places=2)
        self.assertAlmostEqual(section["foreign_invoiced"], 10.0, places=2)
        self.assertIn("action", section)

    def test_get_items_from_invoices_default_exclusion(self):
        invoice = self._create_customer_invoice(quantity=1.0, price_unit=200.0)
        self._post(invoice)
        items = self.project._get_items_from_invoices()
        self.assertAlmostEqual(items["revenues"]["total"]["invoiced"], 200.0, places=2)
        self.assertAlmostEqual(items["revenues"]["total"]["foreign_invoiced"], 10.0, places=2)
