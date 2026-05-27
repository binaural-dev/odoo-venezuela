# -*- coding: utf-8 -*-
import logging
from unittest.mock import patch
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError
from odoo import Command

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "test_create_invoice")
class TestCreateInvoiceFromPicking(TransactionCase):
    """
    Tests for create_invoice and create_multi_invoice methods
    on stock.picking.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # --- Currencies ---
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_usd.active = True

        cls.currency_vef = cls.env.ref("base.VEF")
        cls.currency_vef.active = True

        # --- Company ---
        cls.company = cls.env.company
        cls.company.write({
            "currency_id": cls.currency_vef.id,
            "foreign_currency_id": cls.currency_usd.id,
        })

        # --- Journal (required by create_invoice / create_multi_invoice) ---
        cls.sale_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.sale_journal:
            cls.sale_journal = cls.env["account.journal"].create({
                "name": "Customer Invoices Test",
                "type": "sale",
                "code": "TSINV",
                "company_id": cls.company.id,
            })
        cls.company.customer_journal_id = cls.sale_journal.id

        # --- Tax ---
        cls.sale_tax = cls.env["account.tax"].create({
            "name": "Tax 16%",
            "amount": 16,
            "type_tax_use": "sale",
            "company_id": cls.company.id,
        })
        cls.company.account_sale_tax_id = cls.sale_tax.id

        # --- Income Account (required for invoice lines) ---
        cls.income_account = cls.env["account.account"].create({
            "name": "Test Income Account",
            "code": "TINC001",
            "account_type": "income",
            "company_ids": [Command.set([cls.company.id])],
        })

        # --- Partner & Product ---
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner"})
        cls.product = cls.env["product.product"].create({
            "name": "Test Product",
            "type": "consu",
            "lst_price": 100.0,
            "list_price": 100.0,
            "property_account_income_id": cls.income_account.id,
            "taxes_id": [Command.clear()],
            "supplier_taxes_id": [Command.clear()],
        })

        # --- Pricelists ---
        cls.pricelist_usd = cls.env["product.pricelist"].create({
            "name": "Tarifa USD",
            "currency_id": cls.currency_usd.id,
            "company_id": cls.company.id,
        })

        cls.pricelist_ves = cls.env["product.pricelist"].create({
            "name": "Tarifa VES",
            "currency_id": cls.currency_vef.id,
            "company_id": cls.company.id,
        })

    # =========================================================================
    # Helpers
    # =========================================================================

    def _create_sale_order(self, pricelist=None, qty=1, price_unit=100.0):
        """Create and confirm a sale order with document='dispatch_guide',
        return its picking in done state."""
        vals = {
            "partner_id": self.partner.id,
            "document": "dispatch_guide",
            "date_order": "2026-02-01",
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": qty,
                "price_unit": price_unit,
                "tax_ids": [Command.clear()],
            })],
        }
        if pricelist:
            vals["pricelist_id"] = pricelist.id
        so = self.env["sale.order"].create(vals)
        so.action_confirm()

        picking = so.picking_ids
        picking.move_ids.write({"quantity": qty, "picked": True})
        picking.button_validate()
        return picking

    # =========================================================================
    # create_invoice tests
    # =========================================================================

    def test_create_invoice_basic(self):
        """create_invoice creates an out_invoice and sets state to 'invoiced'."""
        picking = self._create_sale_order(pricelist=self.pricelist_ves)

        invoice = picking.create_invoice()

        self.assertTrue(invoice, "Invoice should be created")
        self.assertEqual(invoice.move_type, "out_invoice")
        self.assertEqual(invoice.partner_id, self.partner)
        self.assertEqual(picking.state_guide_dispatch, "invoiced")

    def test_create_invoice_with_usd_pricelist(self):
        """create_invoice passes pricelist_id from sale order when available."""
        picking = self._create_sale_order(pricelist=self.pricelist_usd)

        invoice = picking.create_invoice()

        self.assertEqual(
            invoice.pricelist_id, self.pricelist_usd,
            "Invoice should have the USD pricelist from the sale order"
        )

    def test_create_invoice_with_ves_pricelist(self):
        """create_invoice passes VES pricelist correctly."""
        picking = self._create_sale_order(pricelist=self.pricelist_ves)

        invoice = picking.create_invoice()

        self.assertEqual(
            invoice.pricelist_id, self.pricelist_ves,
            "Invoice should have the VES pricelist from the sale order"
        )

    def test_create_invoice_no_journal_raises(self):
        """create_invoice raises UserError if customer_journal_id is not configured."""
        picking = self._create_sale_order(pricelist=self.pricelist_ves)
        self.company.customer_journal_id = False

        with self.assertRaises(UserError):
            picking.create_invoice()

        # Restore for other tests
        self.company.customer_journal_id = self.sale_journal.id

    def test_create_invoice_sets_from_picking(self):
        """Invoice created from picking should have from_picking=True."""
        picking = self._create_sale_order(pricelist=self.pricelist_ves)

        invoice = picking.create_invoice()

        self.assertTrue(invoice.from_picking, "Invoice should be marked as from_picking")

    def test_create_invoice_origin_is_sale_order_name(self):
        """For outgoing pickings with a sale order, origin should be the SO name."""
        picking = self._create_sale_order(pricelist=self.pricelist_ves)
        expected_origin = picking.sale_id.name

        invoice = picking.create_invoice()

        self.assertEqual(invoice.invoice_origin, expected_origin)

    def test_create_invoice_invoice_lines(self):
        """Invoice should have at least one line with the correct product."""
        picking = self._create_sale_order(pricelist=self.pricelist_ves, qty=3, price_unit=50.0)

        invoice = picking.create_invoice()

        self.assertTrue(invoice.invoice_line_ids, "Invoice should have lines")
        line = invoice.invoice_line_ids[0]
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.quantity, 3.0)
        self.assertEqual(line.price_unit, 50.0)

    def test_create_invoice_updates_sale_order_status(self):
        """After creating invoice, the sale order should be marked as invoiced."""
        picking = self._create_sale_order(pricelist=self.pricelist_ves)

        picking.create_invoice()

        self.assertEqual(picking.sale_id.invoice_status, "invoiced")

    # =========================================================================
    # create_multi_invoice tests
    # =========================================================================

    def test_create_multi_invoice_basic(self):
        """create_multi_invoice creates one combined invoice for multiple pickings."""
        picking1 = self._create_sale_order(pricelist=self.pricelist_ves)
        picking2 = self._create_sale_order(pricelist=self.pricelist_ves)
        pickings = picking1 | picking2

        invoice = picking1.create_multi_invoice(pickings)

        self.assertTrue(invoice, "Combined invoice should be created")
        self.assertEqual(invoice.move_type, "out_invoice")
        self.assertEqual(picking1.state_guide_dispatch, "invoiced")
        self.assertEqual(picking2.state_guide_dispatch, "invoiced")

    def test_create_multi_invoice_same_pricelist(self):
        """Combined invoice gets the shared pricelist assigned."""
        picking1 = self._create_sale_order(pricelist=self.pricelist_usd)
        picking2 = self._create_sale_order(pricelist=self.pricelist_usd)
        pickings = picking1 | picking2

        invoice = picking1.create_multi_invoice(pickings)

        self.assertEqual(
            invoice.pricelist_id, self.pricelist_usd,
            "Combined invoice should use the shared USD pricelist"
        )

    def test_create_multi_invoice_different_pricelist_raises(self):
        """create_multi_invoice raises UserError when pickings have different pricelists."""
        picking1 = self._create_sale_order(pricelist=self.pricelist_usd)
        picking2 = self._create_sale_order(pricelist=self.pricelist_ves)
        pickings = picking1 | picking2

        with self.assertRaises(UserError):
            picking1.create_multi_invoice(pickings)

    def test_create_multi_invoice_no_journal_raises(self):
        """create_multi_invoice raises UserError if journal not configured."""
        picking1 = self._create_sale_order(pricelist=self.pricelist_ves)
        picking2 = self._create_sale_order(pricelist=self.pricelist_ves)
        pickings = picking1 | picking2
        self.company.customer_journal_id = False

        with self.assertRaises(UserError):
            picking1.create_multi_invoice(pickings)

        # Restore
        self.company.customer_journal_id = self.sale_journal.id

    def test_create_multi_invoice_origin_contains_all_names(self):
        """Invoice origin should contain references from all pickings."""
        picking1 = self._create_sale_order(pricelist=self.pricelist_ves)
        picking2 = self._create_sale_order(pricelist=self.pricelist_ves)
        pickings = picking1 | picking2

        invoice = picking1.create_multi_invoice(pickings)

        # Origin should contain both sale order names
        for picking in pickings:
            so_name = picking.sale_id.name
            self.assertIn(
                so_name, invoice.invoice_origin,
                f"Invoice origin should contain '{so_name}'"
            )

    def test_create_multi_invoice_transfer_ids(self):
        """Combined invoice should reference all pickings in transfer_ids."""
        picking1 = self._create_sale_order(pricelist=self.pricelist_ves)
        picking2 = self._create_sale_order(pricelist=self.pricelist_ves)
        pickings = picking1 | picking2

        invoice = picking1.create_multi_invoice(pickings)

        self.assertEqual(
            invoice.transfer_ids, pickings,
            "Invoice transfer_ids should contain all pickings"
        )

    def test_create_multi_invoice_no_pricelist(self):
        """When pickings have no pricelist, invoice should still be created without pricelist."""
        # Create pickings without sale orders (directly)
        picking_type = self.env.ref("stock.picking_type_out")
        location_src = self.env.ref("stock.stock_location_stock")
        location_dest = self.env.ref("stock.stock_location_customers")

        picking1 = self.env["stock.picking"].create({
            "partner_id": self.partner.id,
            "picking_type_id": picking_type.id,
            "location_id": location_src.id,
            "location_dest_id": location_dest.id,
            "move_ids": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "location_id": location_src.id,
                "location_dest_id": location_dest.id,
            })],
        })
        picking1.action_confirm()
        picking1.move_ids.write({"quantity": 1, "picked": True})
        picking1.button_validate()

        picking2 = self.env["stock.picking"].create({
            "partner_id": self.partner.id,
            "picking_type_id": picking_type.id,
            "location_id": location_src.id,
            "location_dest_id": location_dest.id,
            "move_ids": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 2,
                "location_id": location_src.id,
                "location_dest_id": location_dest.id,
            })],
        })
        picking2.action_confirm()
        picking2.move_ids.write({"quantity": 2, "picked": True})
        picking2.button_validate()

        pickings = picking1 | picking2
        invoice = picking1.create_multi_invoice(pickings)

        self.assertTrue(invoice, "Invoice should be created even without explicit pricelist")

    # =========================================================================
    # action_view_invoice context handling tests
    # =========================================================================

    def test_action_view_invoice_parses_string_context(self):
        """Regression: action context may come as a python-literal string."""
        picking = self._create_sale_order(pricelist=self.pricelist_ves)
        invoice = picking.create_invoice()

        fake_action = {
            "views": [(False, "list"), (False, "form")],
            "context": "{'default_move_type': 'out_invoice', 'default_filter_partner': 'customer'}",
        }

        with patch.object(type(self.env["ir.actions.actions"]), "_for_xml_id", return_value=fake_action):
            action = picking.action_view_invoice(invoices=invoice)

        self.assertEqual(action["res_id"], invoice.id)
        self.assertEqual(action["context"].get("default_filter_partner"), "customer")
        self.assertEqual(action["context"].get("default_partner_id"), picking.partner_id.id)

    def test_action_view_invoice_ignores_non_dict_context(self):
        """If context evaluates to a non-dict value, method should not crash."""
        picking = self._create_sale_order(pricelist=self.pricelist_ves)
        invoice = picking.create_invoice()

        fake_action = {
            "views": [(False, "list"), (False, "form")],
            "context": "'invalid_context'",
        }

        with patch.object(type(self.env["ir.actions.actions"]), "_for_xml_id", return_value=fake_action):
            action = picking.action_view_invoice(invoices=invoice)

        self.assertEqual(action["res_id"], invoice.id)
        self.assertEqual(action["context"].get("default_move_type"), "out_invoice")
        self.assertEqual(action["context"].get("default_partner_id"), picking.partner_id.id)
