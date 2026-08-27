# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged
from odoo import Command


@tagged("post_install", "-at_install", "test_stock_picking_control_number")
class TestStockPickingControlNumber(TransactionCase):
    """Coverage for the dispatch guide control number (pre-printed paper
    numbering) reservation logic added to stock.picking."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_usd.active = True
        cls.currency_vef = cls.env.ref("base.VEF")
        cls.currency_vef.active = True

        cls.company = cls.env.company
        cls.company.write({
            "currency_id": cls.currency_vef.id,
            "foreign_currency_id": cls.currency_usd.id,
            "dispatch_guide_control_number_max_lines": 2,
        })

        cls.sale_journal = cls.env["account.journal"].create({
            "name": "CN Sale Journal",
            "type": "sale",
            "code": "CNSJ",
            "company_id": cls.company.id,
        })
        cls.company.customer_journal_id = cls.sale_journal.id

        cls.sale_tax = cls.env["account.tax"].create({
            "name": "CN Sale Tax 16%",
            "amount": 16,
            "type_tax_use": "sale",
            "company_id": cls.company.id,
        })
        cls.company.account_sale_tax_id = cls.sale_tax.id

        cls.income_account = cls.env["account.account"].create({
            "name": "CN Income",
            "code": "CNINC",
            "account_type": "income",
            "company_ids": [Command.set([cls.company.id])],
        })

        cls.partner = cls.env["res.partner"].create({"name": "CN Partner"})
        cls.product = cls.env["product.product"].create({
            "name": "CN Product",
            "type": "consu",
            "lst_price": 100.0,
            "property_account_income_id": cls.income_account.id,
            "taxes_id": [Command.clear()],
            "supplier_taxes_id": [Command.clear()],
        })

        cls.pricelist_ves = cls.env["product.pricelist"].create({
            "name": "CN VES Pricelist",
            "currency_id": cls.currency_vef.id,
            "company_id": cls.company.id,
        })

    def _create_outgoing_picking(self, line_count, validate=True):
        order_lines = [
            Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "price_unit": 100.0,
                "tax_ids": [Command.clear()],
            })
            for _ in range(line_count)
        ]
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "document": "dispatch_guide",
            "pricelist_id": self.pricelist_ves.id,
            "order_line": order_lines,
        })
        so.action_confirm()
        picking = so.picking_ids
        if validate:
            picking.move_ids.write({"quantity": 1, "picked": True})
            picking.button_validate()
        return picking

    # ── Gating ──

    def test_no_control_numbers_when_not_dispatch_guide_controls(self):
        picking = self._create_outgoing_picking(1, validate=False)
        picking.document = False
        picking.is_dispatch_guide = False
        self.assertFalse(picking.dispatch_guide_controls)
        picking._assign_control_numbers()
        self.assertFalse(picking.control_number_ids)

    # ── Sheet count edge cases ──

    def test_zero_lines_reserves_one_sheet(self):
        picking = self._create_outgoing_picking(1, validate=False)
        picking.move_ids.unlink()
        picking.write({"state": "done", "document": "dispatch_guide"})
        picking._compute_dispatch_guide_controls()
        self.assertTrue(picking.dispatch_guide_controls)
        picking._assign_control_numbers()
        self.assertEqual(len(picking.control_number_ids), 1)

    def test_one_line_reserves_one_sheet(self):
        picking = self._create_outgoing_picking(1)
        self.assertEqual(len(picking.control_number_ids), 1)
        self.assertEqual(picking.control_number_ids.sheet_number, 1)

    def test_exactly_max_reserves_one_sheet(self):
        picking = self._create_outgoing_picking(2)
        self.assertEqual(len(picking.control_number_ids), 1)

    def test_max_plus_one_reserves_two_sheets(self):
        picking = self._create_outgoing_picking(3)
        self.assertEqual(len(picking.control_number_ids), 2)
        self.assertEqual(sorted(picking.control_number_ids.mapped("sheet_number")), [1, 2])

    def test_exact_multiple_of_max_reserves_exact_sheets(self):
        picking = self._create_outgoing_picking(4)
        self.assertEqual(len(picking.control_number_ids), 2)

    def test_max_lines_differs_per_company(self):
        other_company = self.env["res.company"].create({
            "name": "CN Other Company",
            "dispatch_guide_control_number_max_lines": 10,
        })
        picking = self._create_outgoing_picking(3)
        other_picking = self.env["stock.picking"].new({"company_id": other_company.id})
        self.assertEqual(picking._get_control_number_max_lines(), 2)
        self.assertEqual(other_picking._get_control_number_max_lines(), 10)

    def test_default_max_lines_when_unset(self):
        blank_company = self.env["res.company"].create({"name": "CN Blank Company"})
        self.assertEqual(
            blank_company.dispatch_guide_control_number_max_lines, 15
        )

    # ── Idempotency (never overwrite) ──

    def test_assign_control_numbers_is_idempotent(self):
        picking = self._create_outgoing_picking(1)
        existing_numbers = picking.control_number_ids.mapped("number")
        picking._assign_control_numbers()
        self.assertEqual(picking.control_number_ids.mapped("number"), existing_numbers)

    # ── Sequence isolation per company ──

    def test_control_number_sequence_isolated_per_company(self):
        other_company = self.env["res.company"].create({"name": "CN Seq Other Company"})
        picking = self._create_outgoing_picking(1)
        other_picking = self.env["stock.picking"].new({"company_id": other_company.id})
        main_sequence = picking._get_control_number_sequence()
        other_sequence = other_picking._get_control_number_sequence()
        self.assertNotEqual(main_sequence, other_sequence)
        self.assertEqual(other_sequence.company_id, other_company)

    def test_get_control_number_sequence_creates_when_missing(self):
        picking = self._create_outgoing_picking(1)
        self.env["ir.sequence"].search(
            [("code", "=", "stock.picking.control.number"),
             ("company_id", "=", self.company.id)]
        ).unlink()
        sequence = picking._get_control_number_sequence()
        self.assertEqual(sequence.code, "stock.picking.control.number")

    # ── Regression: guide_number assignment (existing behaviour) not broken ──

    def test_action_done_still_sets_guide_number_alongside_control_numbers(self):
        picking = self._create_outgoing_picking(1)
        self.assertTrue(picking.guide_number)
        self.assertTrue(picking.control_number_ids)
