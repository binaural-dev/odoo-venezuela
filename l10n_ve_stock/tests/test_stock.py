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
        self.env["product.product"].create({"name": "Prod1", "barcode": "123456"})
        with self.assertRaises(ValidationError):
            self.env["product.product"].create({"name": "Prod2", "barcode": "123456"})


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockQuant(TransactionCase):
    def test_is_physical_location_computed_correctly(self):
        loc1 = self.env["stock.location"].create({"name": "Loc1", "usage": "internal"})
        loc2 = self.env["stock.location"].create({"name": "Loc2", "usage": "internal"})
        product_tmpl = self.env["product.template"].create(
            {"name": "Prod", "physical_location_id": loc1.id}
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