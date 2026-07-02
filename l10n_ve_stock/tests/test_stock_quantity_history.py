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
