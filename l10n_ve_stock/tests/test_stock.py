import logging
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockLocation(TransactionCase):
    def test_priority_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self.env["stock.location"].create({
                "name": "NegLoc",
                "usage": "internal",
                "priority": -1,
            })


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockMoveLine(TransactionCase):
    def test_get_fields_stock_barcode_includes_priority(self):
        fields = self.env["stock.move.line"]._get_fields_stock_barcode()
        self.assertIn("priority_location", fields)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductBarcode(TransactionCase):
    def test_duplicate_barcode_same_company(self):
        self.env["product.product"].create({"name": "Prod1", "barcode": "123456", 'type': 'consu',})
        with self.assertRaises(ValidationError):
            self.env["product.product"].create({"name": "Prod2", "barcode": "123456", 'type': 'consu',})


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockQuant(TransactionCase):
    def test_is_physical_location_computed_correctly(self):
        loc1 = self.env["stock.location"].create({"name": "Loc1", "usage": "internal"})
        loc2 = self.env["stock.location"].create({"name": "Loc2", "usage": "internal"})
        product_tmpl = self.env["product.template"].create(
            {"name": "Prod", "physical_location_id": loc1.id, 'type': 'consu', 'is_storable': True}
        )
        product = product_tmpl.product_variant_id
        quant1 = self.env["stock.quant"].create(
            {"product_id": product.id, "location_id": loc1.id, "quantity": 1}
        )
        self.assertTrue(quant1.is_physical_location)
        quant2 = self.env["stock.quant"].create(
            {"product_id": product.id, "location_id": loc2.id, "quantity": 1}
        )
        self.assertFalse(quant2.is_physical_location)



@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockLocationGetWarehouse(TransactionCase):
    def test_get_warehouse(self):
        warehouse = self.env["stock.warehouse"].create({"name": "Get WH", "code": "GWH"})
        shelf = self.env["stock.location"].create(
            {"name": "Shelf", "location_id": warehouse.lot_stock_id.id, "usage": "internal"}
        )
        self.assertEqual(shelf.get_warehouse(), warehouse)
        self.assertFalse(self.env["stock.location"].get_warehouse())


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockQuantAlterLocations(TransactionCase):
    def test_product_alter_location_ids(self):
        warehouse = self.env["stock.warehouse"].create({"name": "Quant WH", "code": "QAW"})
        product = self.env["product.product"].create(
            {"name": "Quant Alter Product", "type": "consu", "is_storable": True}
        )
        quant = self.env["stock.quant"].create(
            {"product_id": product.id, "location_id": warehouse.lot_stock_id.id, "quantity": 2}
        )
        self.assertFalse(quant.product_alter_location_ids)
        new_quant = self.env["stock.quant"].new({"product_id": product.id})
        self.assertEqual(new_quant.product_alter_location_ids._origin, quant)
        self.assertFalse(self.env["stock.quant"].new({}).product_alter_location_ids)
