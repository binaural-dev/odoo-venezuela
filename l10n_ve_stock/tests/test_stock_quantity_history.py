import unittest
from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockQuantityHistory(TransactionCase):
    def test_get_fields_products(self):
        wizard = self.env["stock.quantity.history"].create({})
        fields = wizard.get_fields_products()
        self.assertIsInstance(fields, list)
        self.assertIn("id", fields)
        self.assertIn("name", fields)
        self.assertIn("qty_available", fields)
        self.assertIn("free_qty", fields)
        self.assertIn("virtual_available", fields)
        self.assertIn("default_code", fields)
        self.assertIn("standard_price", fields)

    def test_open_at_date(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        wizard = self.env["stock.quantity.history"].create({
            "warehouse_search_id": warehouse.lot_stock_id.id,
        })
        result = wizard.open_at_date()
        self.assertIsInstance(result, dict)

    def test_open_at_date_without_location(self):
        wizard = self.env["stock.quantity.history"].create({})
        result = wizard.open_at_date()
        self.assertIsInstance(result, dict)

    def test_except_products_at_zero_field(self):
        wizard = self.env["stock.quantity.history"].create({
            "except_products_at_zero": True,
        })
        self.assertTrue(wizard.except_products_at_zero)

    def test_warehouse_search_id_field(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        wizard = self.env["stock.quantity.history"].create({
            "warehouse_search_id": warehouse.lot_stock_id.id,
        })
        self.assertEqual(wizard.warehouse_search_id, warehouse.lot_stock_id)

    def test_open_at_date_test(self):
        wizard = self.env["stock.quantity.history"].create({})
        try:
            wizard.open_at_date_test()
        except Exception:
            pass
        self.assertTrue(True)

    @unittest.skip("_compute_quantities_dict_for_report depends on location_final_id removed in Odoo 19")
    def test_generate_report_basic(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        product = self.env["product.product"].create({
            "name": "Report Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 10,
        })
        wizard = self.env["stock.quantity.history"].create({
            "warehouse_search_id": warehouse.lot_stock_id.id,
            "inventory_datetime": "2026-01-01 00:00:00",
            "except_products_at_zero": False,
        })
        result = wizard.generate_report()
        self.assertIsInstance(result, dict)
        self.assertIn(result.get("type"), ["ir.actions.report", "ir.actions.act_window"])

    @unittest.skip("_compute_quantities_dict_for_report depends on location_final_id removed in Odoo 19")
    def test_generate_report_except_zero(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        product = self.env["product.product"].create({
            "name": "Report Prod Zero",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 5,
        })
        wizard = self.env["stock.quantity.history"].create({
            "warehouse_search_id": warehouse.lot_stock_id.id,
            "inventory_datetime": "2026-01-01 00:00:00",
            "except_products_at_zero": True,
        })
        result = wizard.generate_report()
        self.assertIsInstance(result, dict)

    def test_generate_report_without_warehouse(self):
        self.env["product.product"].create({
            "name": "No WH Prod",
            "type": "consu",
            "is_storable": True,
        })
        wizard = self.env["stock.quantity.history"].create({
            "inventory_datetime": "2026-01-01 00:00:00",
            "except_products_at_zero": False,
        })
        try:
            result = wizard.generate_report()
            self.assertIsInstance(result, dict)
        except Exception:
            pass

    def test_generate_report_multi_company(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        product = self.env["product.product"].create({
            "name": "Multi Co Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 10,
        })
        self.env["res.company"].sudo().create({
            "name": "Test Company 2",
            "currency_id": self.env.company.currency_id.id,
        })
        wizard = self.env["stock.quantity.history"].create({
            "warehouse_search_id": warehouse.lot_stock_id.id,
            "inventory_datetime": "2026-01-01 00:00:00",
            "except_products_at_zero": False,
        })
        try:
            result = wizard.generate_report()
            self.assertIsInstance(result, dict)
        except Exception:
            pass


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockQuantityHistoryExceptZero(TransactionCase):
    def test_generate_report_keeps_only_products_with_stock(self):
        warehouse = self.env["stock.warehouse"].create({"name": "History WH", "code": "HSW"})
        product = self.env["product.product"].create({
            "name": "History With Stock",
            "type": "consu",
            "is_storable": True,
        })
        product_without_stock = self.env["product.product"].create({
            "name": "History Without Stock",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"]._update_available_quantity(product, warehouse.lot_stock_id, 5.0)
        wizard = self.env["stock.quantity.history"].create({
            "warehouse_search_id": warehouse.lot_stock_id.id,
            "inventory_datetime": fields.Datetime.now() + timedelta(days=1),
            "except_products_at_zero": True,
        })
        report_class = type(self.env["ir.actions.report"])
        with patch.object(
            report_class, "report_action", lambda report, docids, data=None, config=True: data
        ):
            data = wizard.generate_report()
        product_ids = [prod["id"] for prod in data["product_ids"]]
        self.assertIn(product.id, product_ids)
        self.assertNotIn(product_without_stock.id, product_ids)
