# -*- coding: utf-8 -*-
from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TestDonationCommon


@tagged("post_install", "-at_install", "l10n_ve_donation")
class TestDonationStockPicking(TestDonationCommon):
    """`is_donation` and the donation rules that `l10n_ve_donation` adds to
    `stock.picking`: menu default, transfer reason, validation, delivery
    configuration errors and the cost of the delivery certificate."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reason_donation = cls.env.ref("l10n_ve_stock_account.transfer_reason_donation")
        cls.reason_sale = cls.env.ref("l10n_ve_stock_account.transfer_reason_sale")
        cls.reason_self_consumption = cls.env.ref(
            "l10n_ve_stock_account.transfer_reason_self_consumption"
        )

    def _create_regular_picking(self):
        picking_type = self.warehouse_normal.out_type_id
        return self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
        })

    def _create_donation_sale_picking(self):
        order = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "is_donation": True,
            "document": "invoice",
            "order_line": [Command.create({
                "product_id": self.product_storable.id,
                "product_uom_qty": 1,
                "price_unit": 100.0,
            })],
        })
        picking_type = self.env.ref("stock.picking_type_out")
        location_customers = self.env.ref("stock.stock_location_customers")
        return self.env["stock.picking"].create({
            "partner_id": order.partner_id.id,
            "picking_type_id": picking_type.id,
            "location_id": picking_type.default_location_src_id.id,
            "location_dest_id": location_customers.id,
            "sale_id": order.id,
        })

    # ── is_donation ──

    def test_is_donation_follows_the_sale_order(self):
        picking = self._create_donation_sale_picking()
        self.assertTrue(picking.is_donation)
        picking.sale_id.is_donation = False
        self.assertFalse(picking.is_donation)

    def test_is_donation_is_false_by_default(self):
        picking = self._create_regular_picking()
        self.assertFalse(picking.is_donation)

    def test_is_donation_kept_without_sale_order(self):
        picking = self._create_donation_picking()
        self.assertTrue(picking.is_donation)
        picking.write({"partner_id": self.partner.id})
        self.assertTrue(picking.is_donation)

    def test_donation_menu_context_marks_the_new_picking(self):
        Picking = self.env["stock.picking"]
        self.assertTrue(
            Picking.with_context(donation_menu=True).default_get(["is_donation"])["is_donation"]
        )
        self.assertFalse(Picking.default_get(["is_donation"]).get("is_donation"))
        # A `default_is_donation` is NOT what the menu uses (it would leak
        # to every record created from the action, e.g. valuation entries).
        self.assertNotIn(
            "default_is_donation",
            self.env.ref("l10n_ve_donation.action_stock_picking_donation").context,
        )

    # ── transfer reason ──

    def test_donation_delivery_gets_the_donation_reason(self):
        picking = self._create_donation_picking()
        self.assertEqual(picking.transfer_reason_id, self.reason_donation)
        self.assertIn(self.reason_donation, picking.allowed_reason_ids)

    def test_donation_reason_is_added_not_substituted(self):
        """The base list of the picking is kept: the reason is added to it
        (the base computation rewrites any reason that is not allowed)."""
        picking = self._create_donation_picking()
        self.assertIn(self.reason_self_consumption, picking.allowed_reason_ids)

    def test_donation_sale_picking_gets_the_donation_reason(self):
        picking = self._create_donation_sale_picking()
        self.assertEqual(picking.transfer_reason_id, self.reason_donation)
        self.assertIn(self.reason_sale, picking.allowed_reason_ids)

    def test_regular_delivery_keeps_its_reason(self):
        picking = self._create_regular_picking()
        self.assertNotEqual(picking.transfer_reason_id, self.reason_donation)
        self.assertNotIn(self.reason_donation, picking.allowed_reason_ids)

    def test_donation_picking_has_no_dispatch_guide(self):
        picking = self._create_donation_picking(partner=self.partner)
        self.assertFalse(picking.is_dispatch_guide)

    def test_form_view_makes_the_donation_reason_readonly(self):
        arch = self.env["stock.picking"].get_view(
            self.env.ref("l10n_ve_donation.view_picking_form_donation").id, "form"
        )["arch"]
        self.assertIn("is_donation or state == 'done'", arch)

    def test_form_does_not_repeat_fields(self):
        """`l10n_ve_inventory_book` requires a single `is_donation` and a
        single `sale_id` in the picking form."""
        from lxml import etree
        arch = etree.fromstring(
            self.env["stock.picking"].get_view(view_type="form")["arch"]
        )
        for fname in ("is_donation", "sale_id", "picking_type_code"):
            self.assertEqual(len(arch.xpath(f"//field[@name='{fname}']")), 1, fname)

    def test_create_invoice_button_is_hidden_on_a_donation_without_sale(self):
        """The 'Create Invoice' button would issue a regular fiscal invoice
        to the beneficiary of a donation delivery."""
        picking = self._create_donation_picking(partner=self.partner, validate=True)
        self.assertEqual(picking.state, "done")
        self.assertFalse(picking.show_create_invoice)

        # Control: the same done delivery, if it were not a donation, would
        # offer the button.
        picking.is_donation = False
        self.assertTrue(picking.show_create_invoice)

    # ── button_validate ──

    def test_validate_requires_contact_or_reason(self):
        picking = self._create_donation_picking()
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_validate_with_reason_only_is_accepted(self):
        picking = self._create_donation_picking(reason="Hospital campaign", validate=True)
        self.assertEqual(picking.state, "done")

    def test_validate_with_contact_only_is_accepted(self):
        picking = self._create_donation_picking(partner=self.partner, validate=True)
        self.assertEqual(picking.state, "done")

    # ── configuration errors ──

    def test_config_errors_destination_must_be_inventory(self):
        picking = self._create_donation_picking(reason="x")
        picking.location_dest_id = self.env.ref("stock.stock_location_customers")
        picking.move_ids.location_dest_id = self.env.ref("stock.stock_location_customers")
        errors = picking._get_donation_delivery_config_errors()
        self.assertEqual(len(errors), 1)
        with self.assertRaises(UserError):
            picking.button_validate()

    def test_config_errors_real_time_needs_the_valuation_account(self):
        self.location_donation.valuation_account_id = False
        picking = self._create_donation_picking(reason="x")
        self.assertTrue(picking._has_real_time_valuation_moves())
        self.assertEqual(len(picking._get_donation_delivery_config_errors()), 1)

    def test_config_errors_periodic_valuation_does_not_need_the_account(self):
        self.location_donation.valuation_account_id = False
        self.product_categ.property_valuation = "periodic"
        picking = self._create_donation_picking(reason="x")
        self.assertFalse(picking._has_real_time_valuation_moves())
        self.assertEqual(picking._get_donation_delivery_config_errors(), [])

    def test_config_errors_ok_when_configured(self):
        picking = self._create_donation_picking(reason="x")
        self.assertEqual(picking._get_donation_delivery_config_errors(), [])

    def test_config_errors_non_storable_products_are_not_real_time(self):
        service_like = self.env["product.product"].create({
            "name": "Consumable", "type": "consu", "categ_id": self.product_categ.id,
        })
        picking = self._create_donation_picking(reason="x", product=service_like)
        self.assertFalse(picking._has_real_time_valuation_moves())

    # ── certificate ──

    def test_certificate_cost_comes_from_the_move_value(self):
        picking = self._create_donation_picking(quantity=3, partner=self.partner, validate=True)
        rows = picking._get_donation_product_lines()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["unit_cost"], 15.0)
        self.assertEqual(rows[0]["total_value"], 45.0)
        self.assertEqual(picking._get_donation_grand_total(), 45.0)

    def test_certificate_cost_is_stable_after_a_cost_change(self):
        picking = self._create_donation_picking(partner=self.partner, validate=True)
        self.product_storable.standard_price = 99.0
        self.assertEqual(picking._get_donation_grand_total(), 15.0)

    def test_certificate_cost_is_zero_before_validation(self):
        picking = self._create_donation_picking(partner=self.partner)
        self.assertEqual(picking._get_donation_grand_total(), 0.0)

    def test_print_receipt_returns_the_delivery_receipt(self):
        picking = self._create_donation_picking(
            partner=self.partner, reason="Medication for the clinic", validate=True
        )
        report = self.env.ref("l10n_ve_donation.action_donation_receipt_stock_picking")
        action = picking.print_donation_receipt()
        self.assertEqual(action, report.report_action(picking))
        html, _ = self.env["ir.actions.report"]._render_qweb_html(
            "l10n_ve_donation.donation_receipt_template_stock_picking", picking.ids
        )
        self.assertIn(self.partner.name.encode(), html)
        self.assertIn(b"Recibo de Donaci", html)
        self.assertIn(b"Medication for the clinic", html)
        # The detail of the goods is the shared product table, with its total.
        self.assertIn(b"Total at cost", html)

    def test_delivery_receipt_amounts_come_from_the_cost_of_the_goods(self):
        picking = self._create_donation_picking(quantity=2.0, partner=self.partner, validate=True)
        amounts = picking._get_donation_receipt_amounts()
        self.assertAlmostEqual(amounts["amount"], picking._get_donation_grand_total())
        self.assertTrue(amounts["amount"])
        self.assertEqual(amounts["currency"], self.company.currency_id)

    # ── returns ──

    def test_donation_delivery_cannot_be_returned(self):
        picking = self._create_donation_picking(partner=self.partner, validate=True)
        wizard = self.env["stock.return.picking"].with_context(
            active_id=picking.id, active_model="stock.picking"
        ).create({})
        with self.assertRaises(UserError):
            wizard._create_return()

    def test_donation_delivery_is_not_listed_in_the_dispatch_guides(self):
        """The donation delivery certificate replaces the dispatch guide: a
        donation delivery of a standard delivery operation type (the one
        that is listed in the guides) is not listed; without the donation
        mark it is."""
        out_type = self.warehouse_donation.out_type_id
        product = self.product_storable
        location_src = out_type.default_location_src_id
        destination = self.location_donation
        self._create_stock(product, 1, location_src)
        picking = self.env["stock.picking"].create({
            "picking_type_id": out_type.id,
            "location_id": location_src.id,
            "location_dest_id": destination.id,
            "partner_id": self.partner.id,
            "is_donation": True,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 1,
                "product_uom": product.uom_id.id,
                "location_id": location_src.id,
                "location_dest_id": destination.id,
            })],
        })
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.write({"quantity": 1, "picked": True})
        picking.button_validate()
        self.assertEqual(picking.state, "done")
        self.assertEqual(picking.type_delivery_step, "out")
        self.assertFalse(picking.match_guide_dispatch_domain)

        picking.is_donation = False
        self.assertTrue(picking.match_guide_dispatch_domain)

