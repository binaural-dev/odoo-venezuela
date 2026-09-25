# -*- coding: utf-8 -*-
from odoo.tests import tagged
from odoo import Command

from .common import StockAccountTestCommon


@tagged("post_install", "-at_install", "test_account_move_tax_grouped_lines")
class TestAccountMoveTaxGroupedLines(StockAccountTestCommon):
    """Coverage for `account.move._get_tax_grouped_lines()`."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Two distinct sale taxes (beyond the common `sale_tax`) so lines
        # can be grouped by different tax sets.
        cls.tax_a = cls.env["account.tax"].create({
            "name": "Tax Group A 16%",
            "amount": 16,
            "type_tax_use": "sale",
            "company_id": cls.company.id,
            "tax_group_id": cls.tax_group.id,
            "country_id": cls.country_ve.id,
        })
        cls.tax_b = cls.env["account.tax"].create({
            "name": "Tax Group B 8%",
            "amount": 8,
            "type_tax_use": "sale",
            "company_id": cls.company.id,
            "tax_group_id": cls.tax_group.id,
            "country_id": cls.country_ve.id,
        })

        cls.income_account = cls.env["account.account"].search(
            [("account_type", "=", "income"), ("company_ids", "in", cls.company.ids)],
            limit=1,
        ) or cls.env["account.account"].create({
            "name": "Tax Grouped Lines Income",
            "code": "TGLINC01",
            "account_type": "income",
            "company_ids": [Command.set([cls.company.id])],
        })

        cls.partner = cls.env["res.partner"].create({"name": "Tax Grouped Lines Partner"})
        cls.product = cls.env["product.product"].create({
            "name": "Tax Grouped Lines Product",
            "type": "service",
            "property_account_income_id": cls.income_account.id,
        })

        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )

    def _create_invoice(self, lines):
        return self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "journal_id": self.journal.id,
            "invoice_line_ids": [Command.create(line) for line in lines],
        })

    def test_groups_lines_sharing_the_same_taxes(self):
        move = self._create_invoice([
            {"product_id": self.product.id, "quantity": 1, "price_unit": 100.0, "tax_ids": [Command.set([self.tax_a.id])]},
            {"product_id": self.product.id, "quantity": 1, "price_unit": 50.0, "tax_ids": [Command.set([self.tax_a.id])]},
            {"product_id": self.product.id, "quantity": 1, "price_unit": 30.0, "tax_ids": [Command.set([self.tax_b.id])]},
        ])

        groups = move._get_tax_grouped_lines()

        self.assertEqual(len(groups), 2)
        key_a = (self.tax_a.id,)
        key_b = (self.tax_b.id,)
        self.assertIn(key_a, groups)
        self.assertIn(key_b, groups)
        self.assertAlmostEqual(groups[key_a]["base_amount"], 150.0)
        self.assertAlmostEqual(groups[key_b]["base_amount"], 30.0)
        self.assertEqual(groups[key_a]["taxes"], self.tax_a)
        self.assertEqual(groups[key_b]["taxes"], self.tax_b)

    def test_lines_without_taxes_are_grouped_together(self):
        move = self._create_invoice([
            {"product_id": self.product.id, "quantity": 1, "price_unit": 20.0, "tax_ids": [Command.clear()]},
            {"product_id": self.product.id, "quantity": 1, "price_unit": 10.0, "tax_ids": [Command.clear()]},
        ])

        groups = move._get_tax_grouped_lines()

        self.assertEqual(len(groups), 1)
        self.assertIn((), groups)
        self.assertAlmostEqual(groups[()]["base_amount"], 30.0)
