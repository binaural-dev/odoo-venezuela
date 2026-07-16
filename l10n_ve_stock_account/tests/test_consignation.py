# -*- coding: utf-8 -*-
import logging
from unittest.mock import patch
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError
from odoo import Command

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "test_consignation")
class TestConsignationWarehouseAndLocation(TransactionCase):
    """Tests for stock.warehouse (unique constraint, readonly computed)
    and stock.location consignation constraints."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Consignation Customer"})

        cls.consignation_wh = cls.env["stock.warehouse"].create({
            "name": "Consignation Warehouse",
            "code": "CWH",
            "is_consignation_warehouse": True,
        })

    # ── stock.warehouse tests ──

    def test_unique_consignation_warehouse_raises(self):
        with self.assertRaises(ValidationError):
            self.env["stock.warehouse"].create({
                "name": "Second Consignation Warehouse",
                "code": "CWH2",
                "is_consignation_warehouse": True,
            })

    def test_unique_consignation_warehouse_allows_non_consignation(self):
        wh = self.env["stock.warehouse"].create({
            "name": "Normal Warehouse",
            "code": "NWH",
            "is_consignation_warehouse": False,
        })
        self.assertFalse(wh.is_consignation_warehouse)

    def test_readonly_is_consignation_warehouse_mirrors(self):
        self.assertTrue(self.consignation_wh.readonly_is_consignation_warehouse)
        normal_wh = self.env["stock.warehouse"].create({
            "name": "Normal WH",
            "code": "NW2",
            "is_consignation_warehouse": False,
        })
        self.assertFalse(normal_wh.readonly_is_consignation_warehouse)

    def test_unique_consignation_warehouse_allows_update_same(self):
        self.consignation_wh.write({"name": "Updated Consignation WH"})
        self.assertEqual(self.consignation_wh.name, "Updated Consignation WH")

    # ── stock.location tests ──

    def test_location_must_be_internal_in_consignation_wh(self):
        with self.assertRaises(ValidationError):
            self.env["stock.location"].create({
                "name": "View Location in Consignation WH",
                "usage": "view",
                "location_id": self.consignation_wh.view_location_id.id,
                "partner_id": self.partner.id,
            })

    def test_location_must_have_partner_in_consignation_wh(self):
        with self.assertRaises(ValidationError):
            self.env["stock.location"].create({
                "name": "Internal Location No Partner",
                "usage": "internal",
                "location_id": self.consignation_wh.view_location_id.id,
            })

    def test_location_internal_with_partner_allowed(self):
        loc = self.env["stock.location"].create({
            "name": "Internal Location With Partner",
            "usage": "internal",
            "location_id": self.consignation_wh.view_location_id.id,
            "partner_id": self.partner.id,
        })
        self.assertEqual(loc.usage, "internal")
        self.assertEqual(loc.partner_id, self.partner)

    def test_location_compute_is_consignation_warehouse_true(self):
        loc = self.env["stock.location"].create({
            "name": "Test Consignation Loc",
            "usage": "internal",
            "location_id": self.consignation_wh.view_location_id.id,
            "partner_id": self.partner.id,
        })
        self.assertTrue(loc.is_consignation_warehouse)

    def test_location_compute_is_not_consignation_warehouse(self):
        normal_wh = self.env["stock.warehouse"].create({
            "name": "Normal WH",
            "code": "NW3",
            "is_consignation_warehouse": False,
        })
        loc = self.env["stock.location"].create({
            "name": "Normal Location",
            "usage": "internal",
            "location_id": normal_wh.view_location_id.id,
        })
        self.assertFalse(loc.is_consignation_warehouse)

    def test_location_constraint_not_triggered_on_non_consignation_wh(self):
        normal_wh = self.env["stock.warehouse"].create({
            "name": "Another Normal WH",
            "code": "ANWH",
            "is_consignation_warehouse": False,
        })
        loc = self.env["stock.location"].create({
            "name": "View in Normal WH",
            "usage": "view",
            "location_id": normal_wh.view_location_id.id,
        })
        self.assertEqual(loc.usage, "view")


@tagged("post_install", "-at_install", "test_consignation")
class TestConsignationSaleOrder(TransactionCase):
    """Tests for sale.order and sale.order.line consignation logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # --- Currencies (required by l10n_ve_accountant tax computations) ---
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_usd.active = True
        cls.currency_vef = cls.env.ref("base.VEF")
        cls.currency_vef.active = True

        cls.company = cls.env.company
        cls.company.write({
            "currency_id": cls.currency_vef.id,
            "foreign_currency_id": cls.currency_usd.id,
        })

        cls.partner = cls.env["res.partner"].create({
            "name": "Consignation Customer",
            "default_document": "dispatch_guide",
        })

        cls.product = cls.env["product.product"].create({
            "name": "Consignation Product",
            "type": "consu",
            "is_storable": True,
            "lst_price": 100.0,
        })

        cls.service_product = cls.env["product.product"].create({
            "name": "Service Product",
            "type": "service",
            "lst_price": 50.0,
        })

        cls.consignation_wh = cls.env["stock.warehouse"].create({
            "name": "Consignation Warehouse",
            "code": "CWH",
            "is_consignation_warehouse": True,
        })

        cls.normal_wh = cls.env["stock.warehouse"].create({
            "name": "Normal Warehouse",
            "code": "NWH",
            "is_consignation_warehouse": False,
        })

    # ── sale.order: _default_document ──

    def test_default_document_from_partner(self):
        so = self.env["sale.order"].with_context(
            default_partner_id=self.partner.id
        ).create({
            "partner_id": self.partner.id,
            "warehouse_id": self.normal_wh.id,
        })
        self.assertEqual(so.document, "dispatch_guide")

    def test_default_document_no_partner_falls_back_to_invoice(self):
        doc = self.env["sale.order"].with_context(
            default_partner_id=False
        )._default_document()
        self.assertEqual(doc, "invoice")

    def test_onchange_partner_id_sets_document(self):
        self.partner.default_document = "dispatch_guide"
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "warehouse_id": self.normal_wh.id,
        })
        so._onchange_partner_id()
        self.assertEqual(so.document, "dispatch_guide")

    def test_onchange_partner_id_no_partner_falls_back(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "warehouse_id": self.normal_wh.id,
        })
        so.partner_id = False
        so._onchange_partner_id()
        self.assertEqual(so.document, "invoice")

    # ── sale.order: _compute_is_consignation ──
    # (SO with consignation WH but without order_lines does not trigger
    #  _check_consignation_warehouse constraint)

    def test_is_consignation_computed_true(self):
        so = self.env["sale.order"].with_context(
            default_partner_id=self.partner.id
        ).create({
            "partner_id": self.partner.id,
            "warehouse_id": self.consignation_wh.id,
        })
        self.assertTrue(so.is_consignation)

    def test_is_consignation_computed_false(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "warehouse_id": self.normal_wh.id,
        })
        self.assertFalse(so.is_consignation)

    def test_is_consignation_forces_document_to_invoice(self):
        from odoo.tests.common import Form
        so_form = Form(self.env["sale.order"])
        so_form.partner_id = self.partner
        so_form.warehouse_id = self.consignation_wh
        so = so_form.save()
        self.assertEqual(so.document, "invoice")

    # ── sale.order: _check_consignation_warehouse ──

    def test_consignation_constrains_service_product_skipped(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "warehouse_id": self.consignation_wh.id,
            "order_line": [Command.create({
                "product_id": self.service_product.id,
                "product_uom_qty": 999,
            })],
        })
        so._check_consignation_warehouse()

    # Due to product `type='consu'` restriction, storable quants cannot be
    # created.  The following tests intentionally rely on the absence of quants
    # to trigger validation errors.

    def test_constrains_product_not_in_consignation_location(self):
        other = self.env["res.partner"].create({"name": "Other Customer"})
        so = self.env["sale.order"].create({
            "partner_id": other.id,
            "warehouse_id": self.normal_wh.id,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
            })],
        })
        with self.assertRaises(ValidationError):
            so.write({"warehouse_id": self.consignation_wh.id})

    def test_constrains_quantity_exceeds_stock(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "warehouse_id": self.normal_wh.id,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 100,
            })],
        })
        with self.assertRaises(ValidationError):
            so.write({"warehouse_id": self.consignation_wh.id})

    # ── sale.order.line: consignation checks ──

    def test_sale_line_service_skipped_in_consignation(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "warehouse_id": self.consignation_wh.id,
            "order_line": [Command.create({
                "product_id": self.service_product.id,
                "product_uom_qty": 999,
            })],
        })
        so.order_line._check_product_in_consignation()
        so.order_line._check_quantity_in_consignation()

    def test_sale_line_skipped_in_non_consignation_wh(self):
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "warehouse_id": self.normal_wh.id,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 999999,
            })],
        })
        so.order_line._check_product_in_consignation()
        so.order_line._check_quantity_in_consignation()

    def test_sale_line_missing_product_in_consignation_raises(self):
        other = self.env["res.partner"].create({"name": "Other Customer"})
        with self.assertRaises(ValidationError):
            self.env["sale.order"].create({
                "partner_id": other.id,
                "warehouse_id": self.consignation_wh.id,
                "order_line": [Command.create({
                    "product_id": self.product.id,
                    "product_uom_qty": 1,
                })],
            })

    def test_sale_line_excess_qty_in_consignation_raises(self):
        with self.assertRaises(ValidationError):
            self.env["sale.order"].create({
                "partner_id": self.partner.id,
                "warehouse_id": self.consignation_wh.id,
                "order_line": [Command.create({
                    "product_id": self.product.id,
                    "product_uom_qty": 100,
                })],
            })

    # ── sale.order: _onchange_is_consignation (via Form) ──

    def test_onchange_is_consignation_true_switches_to_consignation_wh(self):
        from odoo.tests.common import Form
        so_form = Form(self.env["sale.order"])
        so_form.partner_id = self.partner
        so_form.warehouse_id = self.normal_wh
        so = so_form.save()
        self.assertFalse(so.is_consignation)
        so_form = Form(so)
        so_form.warehouse_id = self.consignation_wh
        so = so_form.save()
        self.assertTrue(so.is_consignation)

    def test_onchange_is_consignation_false_switches_to_normal_wh(self):
        from odoo.tests.common import Form
        so_form = Form(self.env["sale.order"])
        so_form.partner_id = self.partner
        so_form.warehouse_id = self.consignation_wh
        so = so_form.save()
        self.assertTrue(so.is_consignation)
        so_form = Form(so)
        so_form.warehouse_id = self.normal_wh
        so = so_form.save()
        self.assertFalse(so.is_consignation)

    def test_sale_line_product_in_consignation_allowed(self):
        consignation_loc = self.env["stock.location"].create({
            "name": "Consignation Loc",
            "usage": "internal",
            "location_id": self.consignation_wh.view_location_id.id,
            "partner_id": self.partner.id,
        })
        self.env["stock.quant"].with_context(inventory_mode=True).create({
            "product_id": self.product.id,
            "location_id": consignation_loc.id,
            "quantity": 10,
        })
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "warehouse_id": self.consignation_wh.id,
            "order_line": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
            })],
        })
        so.order_line._check_product_in_consignation()

    def test_sale_line_qty_within_stock_allowed(self):
        storable = self.env["product.product"].create({
            "name": "Storable Consignation Product",
            "type": "consu",
            "is_storable": True,
            "lst_price": 100.0,
        })
        consignation_loc = self.env["stock.location"].create({
            "name": "Consignation Loc",
            "usage": "internal",
            "location_id": self.consignation_wh.view_location_id.id,
            "partner_id": self.partner.id,
        })
        self.env["stock.quant"].with_context(inventory_mode=True).create({
            "product_id": storable.id,
            "location_id": consignation_loc.id,
            "quantity": 10,
        })
        so = self.env["sale.order"].create({
            "partner_id": self.partner.id,
            "warehouse_id": self.consignation_wh.id,
            "order_line": [Command.create({
                "product_id": storable.id,
                "product_uom_qty": 5,
            })],
        })
        so.order_line._check_quantity_in_consignation()
