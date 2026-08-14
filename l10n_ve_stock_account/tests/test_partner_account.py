# -*- coding: utf-8 -*-
import logging
from odoo.tests import TransactionCase, tagged
from odoo import Command

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "test_partner")
class TestResPartner(TransactionCase):
    """Tests for res.partner default_document and _get_main_partner."""

    def test_default_document_default_value(self):
        partner = self.env["res.partner"].create({"name": "Test Partner"})
        self.assertEqual(partner.default_document, "invoice")

    def test_default_document_change_to_dispatch_guide(self):
        partner = self.env["res.partner"].create({
            "name": "Test Partner DG",
            "default_document": "dispatch_guide",
        })
        self.assertEqual(partner.default_document, "dispatch_guide")

    def test_default_document_change_back_to_invoice(self):
        partner = self.env["res.partner"].create({
            "name": "Test Partner DG",
            "default_document": "dispatch_guide",
        })
        partner.default_document = "invoice"
        self.assertEqual(partner.default_document, "invoice")

    def test_get_main_partner_returns_self_for_parent(self):
        partner = self.env["res.partner"].create({"name": "Main Partner"})
        result = partner._get_main_partner()
        self.assertEqual(result, partner)

    def test_get_main_partner_returns_parent_for_child(self):
        parent = self.env["res.partner"].create({"name": "Parent Company"})
        child = self.env["res.partner"].create({
            "name": "Child Contact",
            "parent_id": parent.id,
            "type": "contact",
        })
        result = child._get_main_partner()
        self.assertEqual(result, parent)

    def test_get_main_partner_empty_recordset(self):
        empty = self.env["res.partner"]
        result = empty._get_main_partner()
        self.assertEqual(result, empty)


@tagged("post_install", "-at_install", "test_account_move")
class TestAccountMove(TransactionCase):
    """Tests for account.move guide_number computation and free_form printing."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Invoice Partner"})
        cls.product = cls.env["product.product"].create({
            "name": "Test Product",
            "type": "consu",
            "lst_price": 100.0,
        })

    def _create_picking_with_guide(self, guide_number):
        picking_type_out = self.env.ref("stock.picking_type_out")
        location_src = self.env.ref("stock.stock_location_stock")
        location_dest = self.env.ref("stock.stock_location_customers")

        picking = self.env["stock.picking"].create({
            "partner_id": self.partner.id,
            "picking_type_id": picking_type_out.id,
            "location_id": location_src.id,
            "location_dest_id": location_dest.id,
            "guide_number": guide_number,
            "move_ids": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "location_id": location_src.id,
                "location_dest_id": location_dest.id,
            })],
        })
        return picking

    def test_compute_guide_number_single_picking(self):
        picking = self._create_picking_with_guide("GUIDE-001")
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "picking_ids": [Command.set([picking.id])],
        })
        self.assertEqual(invoice.guide_number, "GUIDE-001")

    def test_compute_guide_number_multiple_pickings(self):
        picking1 = self._create_picking_with_guide("GUIDE-001")
        picking2 = self._create_picking_with_guide("GUIDE-002")
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
            "picking_ids": [Command.set([picking1.id, picking2.id])],
        })
        self.assertEqual(invoice.guide_number, "GUIDE-001/GUIDE-002")

    def test_compute_guide_number_no_pickings(self):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
        })
        self.assertEqual(invoice.guide_number, "")

    def test_free_form_copy_number_starts_at_zero(self):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
        })
        self.assertEqual(invoice.free_form_copy_number, 0)

    def test_print_invoice_free_form_increments_counter(self):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
        })
        self.assertEqual(invoice.free_form_copy_number, 0)
        invoice.print_invoice_free_form()
        self.assertEqual(invoice.free_form_copy_number, 1)
        invoice.print_invoice_free_form()
        self.assertEqual(invoice.free_form_copy_number, 2)

    def test_compute_guide_number_updates_when_pickings_change(self):
        picking = self._create_picking_with_guide("GUIDE-AAA")
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
        })
        self.assertEqual(invoice.guide_number, "")
        invoice.write({"picking_ids": [Command.set([picking.id])]})
        self.assertEqual(invoice.guide_number, "GUIDE-AAA")

    def test_free_form_copy_number_not_copied_on_duplicate(self):
        invoice = self.env["account.move"].create({
            "move_type": "out_invoice",
            "partner_id": self.partner.id,
        })
        invoice.print_invoice_free_form()
        self.assertEqual(invoice.free_form_copy_number, 1)
        duplicate = invoice.copy()
        self.assertEqual(duplicate.free_form_copy_number, 0)
