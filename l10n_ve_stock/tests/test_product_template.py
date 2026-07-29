from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductTemplateButtonDummy(TransactionCase):
    def test_button_dummy_returns_true(self):
        tmpl = self.env["product.template"].create({
            "name": "Dummy Template",
            "type": "consu",
        })
        self.assertTrue(tmpl.button_dummy())


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductTemplateCheckListPrice(TransactionCase):
    def test_negative_list_price_raises(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].create({
                "name": "Negative Price",
                "type": "consu",
                "list_price": -10,
            })

    def test_zero_list_price_raises(self):
        with self.assertRaises(ValidationError):
            self.env["product.template"].create({
                "name": "Zero Price",
                "type": "consu",
                "list_price": 0,
            })

    def test_positive_list_price_ok(self):
        tmpl = self.env["product.template"].create({
            "name": "Positive Price",
            "type": "consu",
            "list_price": 100,
        })
        self.assertEqual(tmpl.list_price, 100)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductTemplateCheckTaxesId(TransactionCase):
    def test_single_tax_ok(self):
        tax = self.env["account.tax"].create({
            "name": "Single Tax",
            "amount_type": "percent",
            "amount": 10,
            "company_id": self.env.company.id,
        })
        tmpl = self.env["product.template"].create({
            "name": "Single Tax Product",
            "type": "consu",
            "taxes_id": [(6, 0, [tax.id])],
        })
        self.assertEqual(len(tmpl.taxes_id), 1)

    def test_no_tax_ok(self):
        tmpl = self.env["product.template"].create({
            "name": "No Tax Product",
            "type": "consu",
            "company_id": self.env.company.id,
            "taxes_id": [(5, 0, 0)],
        })
        self.assertEqual(len(tmpl.taxes_id), 0)

    def test_multiple_taxes_raises(self):
        tax1 = self.env["account.tax"].create({
            "name": "Tax A",
            "amount_type": "percent",
            "amount": 10,
            "company_id": self.env.company.id,
        })
        tax2 = self.env["account.tax"].create({
            "name": "Tax B",
            "amount_type": "percent",
            "amount": 20,
            "company_id": self.env.company.id,
        })
        with self.assertRaises(ValidationError):
            self.env["product.template"].create({
                "name": "Multi Tax Product",
                "type": "consu",
                "taxes_id": [(6, 0, [tax1.id, tax2.id])],
            })


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductTemplateComputePricesWithTax(TransactionCase):
    def test_prices_without_tax(self):
        tmpl = self.env["product.template"].create({
            "name": "No Tax Price",
            "type": "consu",
            "company_id": self.env.company.id,
            "list_price": 100,
            "taxes_id": [(5, 0, 0)],
        })
        self.assertEqual(tmpl.price_with_tax, 100)
        self.assertEqual(tmpl.price_without_tax, 100)

    def test_prices_with_tax(self):
        tax = self.env["account.tax"].create({
            "name": "IVA 16",
            "amount_type": "percent",
            "amount": 16,
            "company_id": self.env.company.id,
        })
        tmpl = self.env["product.template"].create({
            "name": "With Tax Price",
            "type": "consu",
            "list_price": 100,
            "taxes_id": [(6, 0, [tax.id])],
        })
        self.assertAlmostEqual(tmpl.price_with_tax, 116, places=2)
        self.assertAlmostEqual(tmpl.price_without_tax, 100, places=2)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductTemplateComputeAvailableQuantity(TransactionCase):
    def setUp(self):
        super().setUp()
        self.warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.location = self.warehouse.lot_stock_id

    def test_available_quantity_use_free_qty(self):
        self.env.company.use_free_qty_odoo = True
        tmpl = self.env["product.template"].create({
            "name": "Free Qty Product",
            "type": "consu",
            "is_storable": True,
        })
        self.assertEqual(tmpl.quantity, tmpl.free_qty)

    def test_available_quantity_not_use_free_qty(self):
        self.env.company.use_free_qty_odoo = False
        tmpl = self.env["product.template"].create({
            "name": "Not Free Qty Product",
            "type": "consu",
            "is_storable": True,
            "physical_location_id": self.location.id,
        })
        product = tmpl.product_variant_id
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": self.location.id,
            "quantity": 25,
        })
        tmpl.invalidate_recordset(["quantity"])
        tmpl._compute_available_quantity()
        self.assertGreaterEqual(tmpl.quantity, 0)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductTemplateFreeQty(TransactionCase):
    def test_compute_free_qty(self):
        tmpl = self.env["product.template"].create({
            "name": "Free Qty Test",
            "type": "consu",
            "is_storable": True,
        })
        self.assertEqual(tmpl.free_qty, 0.0)

    def test_search_free_qty(self):
        domain = self.env["product.template"]._search_free_qty(">", 0)
        self.assertIsInstance(domain, list)
        self.assertEqual(len(domain), 1)
        self.assertEqual(domain[0][0], "product_variant_ids")


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductTemplateAlternateCode(TransactionCase):
    def test_alternate_code_field(self):
        tmpl = self.env["product.template"].create({
            "name": "Alt Code Product",
            "type": "consu",
            "alternate_code": "ALT-001",
        })
        self.assertEqual(tmpl.alternate_code, "ALT-001")


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductTemplatePhysicalLocation(TransactionCase):
    def test_physical_location_field(self):
        loc = self.env["stock.location"].create({
            "name": "Phys Loc",
            "usage": "internal",
        })
        tmpl = self.env["product.template"].create({
            "name": "Phys Loc Product",
            "type": "consu",
            "physical_location_id": loc.id,
        })
        self.assertEqual(tmpl.physical_location_id, loc)

    def test_priority_location_related(self):
        loc = self.env["stock.location"].create({
            "name": "Priority Loc",
            "usage": "internal",
            "priority": 5,
        })
        tmpl = self.env["product.template"].create({
            "name": "Priority Product",
            "type": "consu",
            "physical_location_id": loc.id,
        })
        self.assertEqual(tmpl.priority_location, 5)
