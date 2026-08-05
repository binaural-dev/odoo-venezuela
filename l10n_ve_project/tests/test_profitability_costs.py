# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import L10nVeProjectTestCommon


@tagged("post_install", "-at_install", "l10n_ve_project")
class TestProfitabilityCosts(L10nVeProjectTestCommon):
    """Tests for the foreign amounts of the project profitability costs.

    Product price 100 VEF, USD rate 0.05 (1 USD = 20 VEF): a PO of 2 units has
    a foreign subtotal of 10 USD, so a cost of 200 VEF is 10 USD.
    """

    @staticmethod
    def _section(items, key, section_id):
        return next(item for item in items[key]["data"] if item["id"] == section_id)

    def test_purchase_order_section_before_bill(self):
        po, pol = self._create_purchase_order(quantity=2.0, price_unit=100.0)
        items = self.project._get_profitability_items(False)
        section = self._section(items, "costs", "purchase_order")
        self.assertAlmostEqual(section["billed"], 0.0, places=2)
        self.assertAlmostEqual(section["to_bill"], -200.0, places=2)
        self.assertAlmostEqual(section["foreign_billed"], 0.0, places=2)
        self.assertAlmostEqual(section["foreign_to_bill"], -10.0, places=2)
        self.assertAlmostEqual(items["costs"]["total"]["foreign_to_bill"], -10.0, places=2)

    def test_purchase_order_section_after_partial_bill(self):
        po, pol = self._create_purchase_order(quantity=2.0, price_unit=100.0)
        bill = self._create_bill(quantity=1.0, price_unit=100.0, purchase_line=pol)
        self._post(bill)
        items = self.project._get_profitability_items(False)
        section = self._section(items, "costs", "purchase_order")
        self.assertAlmostEqual(section["billed"], -100.0, places=2)
        self.assertAlmostEqual(section["to_bill"], -100.0, places=2)
        self.assertAlmostEqual(section["foreign_billed"], -5.0, places=2)
        self.assertAlmostEqual(section["foreign_to_bill"], -5.0, places=2)

    def test_other_purchase_costs_draft(self):
        bill = self._create_bill(quantity=1.0, price_unit=200.0)
        self.assertEqual(bill.state, "draft")
        items = self.project._get_profitability_items(False)
        section = self._section(items, "costs", "other_purchase_costs")
        self.assertAlmostEqual(section["billed"], 0.0, places=2)
        self.assertAlmostEqual(section["to_bill"], -200.0, places=2)
        self.assertAlmostEqual(section["foreign_billed"], 0.0, places=2)
        self.assertAlmostEqual(section["foreign_to_bill"], -10.0, places=2)

    def test_other_purchase_costs_posted(self):
        bill = self._create_bill(quantity=1.0, price_unit=200.0)
        self._post(bill)
        items = self.project._get_profitability_items(False)
        section = self._section(items, "costs", "other_purchase_costs")
        self.assertAlmostEqual(section["billed"], -200.0, places=2)
        self.assertAlmostEqual(section["to_bill"], 0.0, places=2)
        self.assertAlmostEqual(section["foreign_billed"], -10.0, places=2)
        self.assertAlmostEqual(section["foreign_to_bill"], 0.0, places=2)

    def test_costs_from_aal(self):
        self.env["account.analytic.line"].create({
            "name": "Extra cost",
            "account_id": self.analytic_account.id,
            "amount": -100.0,
            "foreign_amount": -5.0,
        })
        self.env["account.analytic.line"].create({
            "name": "Extra revenue",
            "account_id": self.analytic_account.id,
            "amount": 50.0,
            "foreign_amount": 2.5,
        })
        items = self.project._get_profitability_items(False)
        cost_section = self._section(items, "costs", "other_costs_aal")
        self.assertAlmostEqual(cost_section["billed"], -100.0, places=2)
        self.assertAlmostEqual(cost_section["to_bill"], 0.0, places=2)
        self.assertAlmostEqual(cost_section["foreign_billed"], -5.0, places=2)
        self.assertAlmostEqual(cost_section["foreign_to_bill"], 0.0, places=2)
        revenue_section = self._section(items, "revenues", "other_revenues_aal")
        self.assertAlmostEqual(revenue_section["invoiced"], 50.0, places=2)
        self.assertAlmostEqual(revenue_section["foreign_invoiced"], 2.5, places=2)

    def test_foreign_totals_sum_of_sections(self):
        po, pol = self._create_purchase_order(quantity=2.0, price_unit=100.0)
        bill = self._create_bill(quantity=1.0, price_unit=100.0, purchase_line=pol)
        self._post(bill)
        other_bill = self._create_bill(quantity=1.0, price_unit=200.0)
        self._post(other_bill)
        items = self.project._get_profitability_items(False)
        for total_key, section_key in (("foreign_billed", "billed"), ("foreign_to_bill", "to_bill")):
            self.assertAlmostEqual(
                items["costs"]["total"][total_key],
                sum(section.get(total_key, 0.0) for section in items["costs"]["data"]),
                places=2,
            )
        self.assertTrue(
            any(section["id"] == "purchase_order" for section in items["costs"]["data"])
        )
        self.assertTrue(
            any(section["id"] == "other_purchase_costs" for section in items["costs"]["data"])
        )

    def test_purchase_order_section_with_draft_bill(self):
        po, pol = self._create_purchase_order(quantity=2.0, price_unit=100.0)
        bill = self._create_bill(quantity=1.0, price_unit=100.0, purchase_line=pol)
        self.assertEqual(bill.state, "draft")
        items = self.project._get_profitability_items(False)
        section = self._section(items, "costs", "purchase_order")
        self.assertAlmostEqual(section["billed"], 0.0, places=2)
        self.assertAlmostEqual(section["to_bill"], -200.0, places=2)
        self.assertAlmostEqual(section["foreign_billed"], 0.0, places=2)
        self.assertAlmostEqual(section["foreign_to_bill"], -10.0, places=2)

    def test_purchase_order_section_with_refund_bill(self):
        po, pol = self._create_purchase_order(quantity=2.0, price_unit=100.0)
        refund = self._create_bill(quantity=1.0, price_unit=100.0, purchase_line=pol, move_type="in_refund")
        self._post(refund)
        items = self.project._get_profitability_items(False)
        section = self._section(items, "costs", "purchase_order")
        self.assertAlmostEqual(section["foreign_billed"], 5.0, places=2)
        self.assertAlmostEqual(section["foreign_to_bill"], -10.0, places=2)

    def test_purchase_order_section_qty_fully_invoiced_amount_mismatch(self):
        """A PO line fully invoiced in quantity may still have a monetary gap.

        Two posted bills cover the full ordered quantity (4/4, so
        ``qty_to_invoice`` is 0) but at a different price than the order, so
        the invoiced amount (440) does not match the order subtotal (400).
        The old quantity-based forecast dropped ``foreign_to_bill`` to 0 in
        this case; the monetary logic must keep reflecting the real gap.
        """
        po, pol = self._create_purchase_order(quantity=4.0, price_unit=100.0)
        bill_1 = self._create_bill(quantity=2.0, price_unit=100.0, purchase_line=pol)
        self._post(bill_1)
        bill_2 = self._create_bill(quantity=2.0, price_unit=120.0, purchase_line=pol)
        self._post(bill_2)
        self.assertEqual(pol.qty_invoiced, pol.product_qty)
        self.assertEqual(pol.qty_to_invoice, 0.0)
        items = self.project._get_profitability_items(False)
        section = self._section(items, "costs", "purchase_order")
        self.assertAlmostEqual(section["foreign_billed"], -22.0, places=2)
        self.assertAlmostEqual(section["foreign_to_bill"], 2.0, places=2)

    def test_purchase_order_section_diverging_rates(self):
        """foreign_billed/foreign_to_bill must reflect the invoice's own
        rate, not the purchase order's rate, when they differ.

        The order is dated 5 days ago at 1 USD = 25 VEF (rate 0.04), so its
        committed foreign subtotal is 8.0 USD. The bill is posted today at
        the common setup rate 1 USD = 20 VEF (rate 0.05), so the amount
        actually invoiced is 10.0 USD. The gap between the two must show up
        in foreign_to_bill instead of being silently dropped.
        """
        past_date = fields.Date.today() - timedelta(days=5)
        self.env["res.currency.rate"].create({
            "currency_id": self.usd.id,
            "rate": 0.04,
            "name": past_date,
            "company_id": self.company.id,
        })
        po, pol = self._create_purchase_order(quantity=2.0, price_unit=100.0, date_order=past_date)
        self.assertAlmostEqual(pol.foreign_subtotal, 8.0, places=2)

        bill = self._create_bill(quantity=2.0, price_unit=100.0, purchase_line=pol)
        self._post(bill)

        items = self.project._get_profitability_items(False)
        section = self._section(items, "costs", "purchase_order")
        self.assertAlmostEqual(section["billed"], -200.0, places=2)
        self.assertAlmostEqual(section["foreign_billed"], -10.0, places=2)
        self.assertAlmostEqual(section["foreign_to_bill"], 2.0, places=2)

    def test_purchase_order_section_diverging_analytic_distribution(self):
        """foreign_billed must use the invoice line's own analytic
        distribution, not the purchase order line's, when they differ."""
        other_account = self.env["account.analytic.account"].create({
            "name": "Other Project",
            "plan_id": self.analytic_plan.id,
            "company_id": self.company.id,
        })
        po, pol = self._create_purchase_order(quantity=2.0, price_unit=100.0)  # 100% al proyecto bajo test
        bill = self._create_bill(
            quantity=2.0, price_unit=100.0, purchase_line=pol,
            analytic_distribution={str(self.analytic_account.id): 50, str(other_account.id): 50},
        )
        self._post(bill)

        items = self.project._get_profitability_items(False)
        section = self._section(items, "costs", "purchase_order")
        self.assertAlmostEqual(section["foreign_billed"], -5.0, places=2)  # 50% de 10.0, no el 100% de la orden

    def test_costs_with_actions(self):
        bill = self._create_bill(quantity=1.0, price_unit=200.0)
        self._post(bill)
        self.env["account.analytic.line"].create({
            "name": "Extra cost",
            "account_id": self.analytic_account.id,
            "amount": -100.0,
            "foreign_amount": -5.0,
        })
        items = self.project._get_profitability_items()
        purchase_section = self._section(items, "costs", "other_purchase_costs")
        self.assertIn("action", purchase_section)
        aal_section = self._section(items, "costs", "other_costs_aal")
        self.assertIn("action", aal_section)

    def test_other_purchase_costs_zero_amount_not_displayed(self):
        bill = self.env["account.move"].create({
            "move_type": "in_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal_purchase.id,
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1.0,
                "price_unit": 100.0,
                "account_id": self.account_expense.id,
                "analytic_distribution": {str(self.analytic_account.id): 0},
            })],
        })
        items = self.project._get_profitability_items(False)
        self.assertFalse(
            any(item["id"] == "other_purchase_costs" for item in items["costs"]["data"])
        )
