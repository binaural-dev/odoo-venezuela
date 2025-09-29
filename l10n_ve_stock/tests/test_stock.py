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
        self.env["product.product"].create({"name": "Prod1", "barcode": "123456", 'type': 'product',})
        with self.assertRaises(ValidationError):
            self.env["product.product"].create({"name": "Prod2", "barcode": "123456", 'type': 'product',})


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockQuant(TransactionCase):
    def test_is_physical_location_computed_correctly(self):
        loc1 = self.env["stock.location"].create({"name": "Loc1", "usage": "internal"})
        loc2 = self.env["stock.location"].create({"name": "Loc2", "usage": "internal"})
        product_tmpl = self.env["product.template"].create(
            {"name": "Prod", "physical_location_id": loc1.id, 'type': 'product'}
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
class TestProductTemplate(TransactionCase):
    def test_check_taxes_id_multiple_taxes_same_company(self):
        tax1 = self.env["account.tax"].create({
            "name": "Tax 1",
            "amount_type": "percent",
            "amount": 10,
            "company_id": self.env.company.id,
        })
        tax2 = self.env["account.tax"].create({
            "name": "Tax 2",
            "amount_type": "percent",
            "amount": 20,
            "company_id": self.env.company.id,
        })
        with self.assertRaises(ValidationError):
            self.env["product.product"].create({
                "name": "Product 1",
                "barcode": "123456",
                "type": 'product',
                "taxes_id": [(6, 0, [tax1.id, tax2.id])],
                "product_tmpl_id": self.env["product.template"].create({
                    "name": "Prod1",
                    "uom_id": self.env.ref('uom.product_uom_unit').id,
                    "uom_po_id": self.env.ref('uom.product_uom_unit').id,
                }).id,
            })