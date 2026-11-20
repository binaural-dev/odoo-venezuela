from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductStock(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.warehouse = cls.env["stock.warehouse"].search([("company_id", "=", cls.company.id)], limit=1)
        cls.stock = cls.warehouse.lot_stock_id
        cls.shelf_a = cls.env["stock.location"].create(
            {"name": "Estante A", "usage": "internal", "location_id": cls.stock.id}
        )
        cls.shelf_b = cls.env["stock.location"].create(
            {"name": "Estante B", "usage": "internal", "location_id": cls.stock.id}
        )
        cls.tax = cls.env["account.tax"].create({"name": "IVA prueba", "amount": 16, "type_tax_use": "sale"})
        cls.product = cls.env["product.product"].create(
            {
                "name": "Producto stock",
                "type": "product",
                "list_price": 100,
                "taxes_id": [(6, 0, cls.tax.ids)],
            }
        )

    def _add_stock(self, location, qty, product=None):
        self.env["stock.quant"]._update_available_quantity(product or self.product, location, qty)

    def test_user_blocked_cannot_create_products(self):
        user = new_test_user(
            self.env,
            login="bloqueado_producto",
            groups="stock.group_stock_user,l10n_ve_stock.group_block_type_inventory_transfers_expeditions",
        )
        with self.assertRaises(UserError):
            self.env["product.product"].with_user(user).create({"name": "No permitido"})

    def test_barcode_unique_by_company(self):
        self.product.barcode = "BIN-0001"
        with self.assertRaises(ValidationError):
            self.env["product.product"].create({"name": "Duplicado", "barcode": "BIN-0001", "list_price": 1})

    def test_barcode_used_by_packaging(self):
        other = self.env["product.product"].create({"name": "Con empaque", "list_price": 1})
        self.env["product.packaging"].create({"name": "Caja", "product_id": other.id, "barcode": "PKG-1"})
        with self.assertRaises(ValidationError):
            self.product.barcode = "PKG-1"

    def test_prices_with_tax(self):
        template = self.product.product_tmpl_id
        self.assertAlmostEqual(template.price_with_tax, 116)
        self.assertAlmostEqual(template.price_without_tax, 100)

        template.taxes_id = False
        template.invalidate_recordset(["price_with_tax", "price_without_tax"])
        self.assertEqual(template.price_with_tax, 100)

    def test_unique_tax_constraint(self):
        second_tax = self.env["account.tax"].create({"name": "IVA 8", "amount": 8, "type_tax_use": "sale"})
        with self.assertRaises(ValidationError):
            self.product.product_tmpl_id.taxes_id = [(6, 0, (self.tax | second_tax).ids)]

    def test_available_quantity_from_warehouse_stock(self):
        self._add_stock(self.stock, 7)
        self._add_stock(self.shelf_a, 3)
        template = self.product.product_tmpl_id

        self.company.use_free_qty_odoo = False
        template._compute_available_quantity()
        self.assertEqual(template.quantity, 10)

        self.company.use_free_qty_odoo = True
        template._compute_available_quantity()
        self.assertEqual(template.quantity, template.free_qty)
        self.assertEqual(template.free_qty, 10)
        self.assertIn(
            template,
            self.env["product.template"].search([("free_qty", ">", 5), ("id", "=", template.id)]),
        )

    def test_quantities_dict_with_location(self):
        self._add_stock(self.shelf_a, 5)
        self._add_stock(self.shelf_b, 2)
        product = self.product.with_context(location=self.shelf_a.id)

        res = product._compute_quantities_dict(None, None, None, location=self.shelf_a)
        self.assertEqual(res[self.product.id]["qty_available"], 5)
        self.assertEqual(res[self.product.id]["free_qty"], 5)

        res = product._compute_quantities_dict(
            None,
            None,
            None,
            from_date=fields.Datetime.now() - timedelta(days=30),
            to_date=fields.Datetime.now() + timedelta(days=1),
            location=self.shelf_a,
        )
        self.assertEqual(res[self.product.id]["qty_available"], 5)

        res = product._compute_quantities_dict(False, False, False, location=self.shelf_a)
        self.assertEqual(res[self.product.id]["qty_available"], 5)

        res = self.product._compute_quantities_dict(None, None, None)
        self.assertEqual(res[self.product.id]["qty_available"], 7)

    def test_quantities_dict_in_the_past(self):
        receipt_type = self.warehouse.in_type_id
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": receipt_type.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.shelf_a.id,
                "move_ids": [
                    (0, 0, {
                        "name": self.product.name,
                        "product_id": self.product.id,
                        "product_uom_qty": 4,
                        "product_uom": self.product.uom_id.id,
                        "location_id": self.env.ref("stock.stock_location_suppliers").id,
                        "location_dest_id": self.shelf_a.id,
                    })
                ],
            }
        )
        picking.action_confirm()
        picking.move_ids.quantity = 4
        picking.button_validate()

        past = fields.Datetime.now() - timedelta(days=1)
        res = self.product.with_context(location=self.shelf_a.id)._compute_quantities_dict(
            None, None, None, to_date=past, location=self.shelf_a
        )
        self.assertEqual(res[self.product.id]["qty_available"], 0)

    def test_quantities_dict_new_record(self):
        new_product = self.env["product.product"].new({"name": "Nuevo"})
        res = new_product._compute_quantities_dict(None, None, None, location=self.shelf_a)
        self.assertEqual(res[new_product.id]["qty_available"], 0)

        res = new_product._compute_quantities_dict_for_report(None, None, None)
        self.assertEqual(res[new_product.id]["free_qty"], 0)

    def test_quantities_dict_for_report(self):
        self._add_stock(self.shelf_a, 6)
        product = self.product.with_context(location=self.shelf_a.id)

        res = product._compute_quantities_dict_for_report(
            None,
            None,
            None,
            from_date=fields.Datetime.now() - timedelta(days=1),
            to_date=fields.Datetime.now() + timedelta(days=1),
        )
        self.assertEqual(res[self.product.id]["qty_available"], 6)

        res = product._compute_quantities_dict_for_report(False, False, False)
        self.assertIn("virtual_available", res[self.product.id])

    def test_location_priority_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            self.shelf_a.priority = -1

    def test_physical_location_reservation(self):
        self.company.use_physical_location = True
        self.product.physical_location_id = self.shelf_b
        self._add_stock(self.shelf_a, 5)
        self._add_stock(self.shelf_b, 5)

        quant_b = self.env["stock.quant"].search(
            [("product_id", "=", self.product.id), ("location_id", "=", self.shelf_b.id)]
        )
        self.assertTrue(quant_b.is_physical_location)
        self.assertIn(self.shelf_a, quant_b.product_alter_location_ids.location_id)

        reserved = self.env["stock.quant"]._update_reserved_quantity(self.product, self.stock, 3)
        self.assertEqual([quant.location_id for quant, _qty in reserved], [self.shelf_b])
        self.assertEqual(quant_b.reserved_quantity, 3)

        unreserved = self.env["stock.quant"]._update_reserved_quantity(self.product, self.stock, -3)
        self.assertEqual(unreserved[0][1], -3)
        self.assertEqual(quant_b.reserved_quantity, 0)

        self.assertEqual(self.env["stock.quant"]._update_reserved_quantity(self.product, self.stock, 0), [])

    def test_physical_location_without_stock_uses_standard_reservation(self):
        self.company.use_physical_location = True
        self.product.physical_location_id = self.shelf_b
        self._add_stock(self.shelf_a, 5)

        def reserved():
            quants = self.env["stock.quant"].search([("product_id", "=", self.product.id)])
            return sum(quants.mapped("reserved_quantity"))

        self.env["stock.quant"]._update_reserved_quantity(self.product, self.stock, 2)
        self.assertEqual(reserved(), 2)

        skipped = self.env["stock.quant"].with_context(skip_physical_location=True)
        skipped._update_reserved_quantity(self.product, self.stock, 1)
        self.assertEqual(reserved(), 3)

    def test_scrap_more_than_available(self):
        self.company.allow_scrap_more_than_available = False
        self._add_stock(self.stock, 1)
        scrap = self.env["stock.scrap"].create(
            {"product_id": self.product.id, "scrap_qty": 5, "location_id": self.stock.id}
        )
        with self.assertRaises(ValidationError):
            scrap.action_validate()

        self.company.allow_scrap_more_than_available = True
        self.company.not_allow_scrap_more_than_what_was_manufactured = True
        scrap.scrap_qty = 1
        scrap.action_validate()
        self.assertEqual(scrap.state, "done")

    def test_settings_store_scrap_option_in_company(self):
        with Form(self.env["res.config.settings"]) as settings:
            settings.allow_scrap_more_than_available = True
        self.assertTrue(self.company.allow_scrap_more_than_available)

    def test_quantity_history_report(self):
        self._add_stock(self.shelf_a, 4)
        self.company.external_report_layout_id = self.env.ref("web.external_layout_standard")
        wizard = self.env["stock.quantity.history"].create(
            {
                "inventory_datetime": fields.Datetime.now() + timedelta(days=1),
                "warehouse_search_id": self.shelf_a.id,
            }
        )
        action = wizard.generate_report()
        self.assertEqual(action["type"], "ir.actions.report")
        product_line = [p for p in action["data"]["product_ids"] if p["id"] == self.product.id]
        self.assertEqual(product_line[0]["qty_available"], 4)
        self.assertEqual(action["data"]["company_id"], self.company.id)

        wizard.except_products_at_zero = True
        action = wizard.generate_report()
        self.assertTrue(all(p["qty_available"] > 0 for p in action["data"]["product_ids"]))
        self.assertEqual(wizard.get_fields_products().count("id"), 1)

        self.assertTrue(wizard.open_at_date())

    def test_list_price_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self.env["product.product"].create({"name": "Sin precio", "list_price": 0})
        with self.assertRaises(ValidationError):
            self.product.list_price = -1

        product = self.env["product.product"].with_context(install_mode=True).create(
            {"name": "Instalación", "list_price": 0}
        )
        self.assertEqual(product.list_price, 0)

    def test_negative_inventory_adjustment_blocked(self):
        self.company.not_allow_negative_inventory_adjustments = True
        quant = self.env["stock.quant"].with_context(inventory_mode=True).create(
            {"product_id": self.product.id, "location_id": self.stock.id, "inventory_quantity": -3}
        )
        with self.assertRaises(ValidationError):
            quant.action_apply_inventory()

        quant.inventory_quantity = 3
        quant.action_apply_inventory()
        self.assertEqual(self.product.with_context(location=self.stock.id).qty_available, 3)

    def test_new_warehouse_operation_type_names(self):
        warehouse = self.env["stock.warehouse"].create({"name": "Almacén nombres", "code": "WNM"})
        self.assertEqual(warehouse.in_type_id.name, "Receipts")
        self.assertEqual(warehouse.int_type_id.name, "Internal Transfers")
