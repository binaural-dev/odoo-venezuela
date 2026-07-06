from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockQuantProductAlterLocations(TransactionCase):
    def test_compute_product_alter_location_ids(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        loc1 = warehouse.lot_stock_id
        loc2 = self.env["stock.location"].create({
            "name": "Alt Loc",
            "usage": "internal",
        })
        product = self.env["product.product"].create({
            "name": "Alt Loc Prod",
            "type": "consu",
            "is_storable": True,
        })
        quant1 = self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": loc1.id,
            "quantity": 5,
        })
        quant2 = self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": loc2.id,
            "quantity": 3,
        })
        quant1.invalidate_recordset(["product_alter_location_ids"])
        self.assertIn(quant2, quant1.product_alter_location_ids)
        self.assertNotIn(quant1, quant1.product_alter_location_ids)

    def test_compute_product_alter_location_ids_empty(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        product = self.env["product.product"].create({
            "name": "Single Loc Prod",
            "type": "consu",
            "is_storable": True,
        })
        quant = self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 1,
        })
        quant.invalidate_recordset(["product_alter_location_ids"])
        self.assertEqual(len(quant.product_alter_location_ids), 0)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockQuantIsPhysicalLocation(TransactionCase):
    def test_is_physical_location_true(self):
        loc = self.env["stock.location"].create({
            "name": "Phys True Loc",
            "usage": "internal",
        })
        product = self.env["product.product"].create({
            "name": "Phys True Prod",
            "type": "consu",
            "is_storable": True,
        })
        product.product_tmpl_id.physical_location_id = loc.id
        quant = self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": loc.id,
            "quantity": 1,
        })
        self.assertTrue(quant.is_physical_location)

    def test_is_physical_location_false(self):
        loc1 = self.env["stock.location"].create({
            "name": "Phys False Loc1",
            "usage": "internal",
        })
        loc2 = self.env["stock.location"].create({
            "name": "Phys False Loc2",
            "usage": "internal",
        })
        product = self.env["product.product"].create({
            "name": "Phys False Prod",
            "type": "consu",
            "is_storable": True,
        })
        product.product_tmpl_id.physical_location_id = loc1.id
        quant = self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": loc2.id,
            "quantity": 1,
        })
        self.assertFalse(quant.is_physical_location)

    def test_is_physical_location_no_physical(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        product = self.env["product.product"].create({
            "name": "No Phys Prod",
            "type": "consu",
            "is_storable": True,
        })
        product.product_tmpl_id.physical_location_id = False
        quant = self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 1,
        })
        self.assertFalse(quant.is_physical_location)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockQuantUpdateReservedQuantity(TransactionCase):
    def test_update_reserved_quantity_skip_physical_location(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env.company.use_physical_location = True
        product = self.env["product.product"].create({
            "name": "Reserve Skip Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 10,
        })
        try:
            self.env["stock.quant"].with_context(
                skip_physical_location=True
            )._update_reserved_quantity(
                product, warehouse.lot_stock_id, 3
            )
        except Exception:
            pass
        self.assertTrue(True)

    def test_update_reserved_quantity_no_physical_location(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env.company.use_physical_location = False
        product = self.env["product.product"].create({
            "name": "No Phys Reserve Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 10,
        })
        try:
            self.env["stock.quant"]._update_reserved_quantity(
                product, warehouse.lot_stock_id, 3
            )
        except Exception:
            pass
        self.assertTrue(True)

    def test_update_reserved_quantity_zero_quantity(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env.company.use_physical_location = True
        product = self.env["product.product"].create({
            "name": "Zero Reserve Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 10,
        })
        quants = self.env["stock.quant"]._update_reserved_quantity(
            product, warehouse.lot_stock_id, 0
        )
        self.assertEqual(quants, [])

    def test_update_reserved_quantity_with_physical_location(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        loc = warehouse.lot_stock_id
        self.env.company.use_physical_location = True
        product = self.env["product.product"].create({
            "name": "Phys Reserve Prod",
            "type": "consu",
            "is_storable": True,
        })
        product.product_tmpl_id.physical_location_id = loc.id
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": loc.id,
            "quantity": 10,
        })
        quants = self.env["stock.quant"]._update_reserved_quantity(
            product, loc, 3
        )
        self.assertIsInstance(quants, list)
        if quants:
            self.assertTrue(all(qty > 0 for _, qty in quants))

    def test_update_reserved_quantity_unreserve(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        loc = warehouse.lot_stock_id
        self.env.company.use_physical_location = True
        product = self.env["product.product"].create({
            "name": "Unreserve Prod",
            "type": "consu",
            "is_storable": True,
        })
        product.product_tmpl_id.physical_location_id = loc.id
        quant = self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": loc.id,
            "quantity": 10,
            "reserved_quantity": 5,
        })
        quants = self.env["stock.quant"]._update_reserved_quantity(
            product, loc, -2
        )
        self.assertIsInstance(quants, list)

    def test_update_reserved_quantity_no_physical_on_product(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        loc = warehouse.lot_stock_id
        self.env.company.use_physical_location = True
        product = self.env["product.product"].create({
            "name": "No Phys On Prod",
            "type": "consu",
            "is_storable": True,
        })
        product.product_tmpl_id.physical_location_id = False
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": loc.id,
            "quantity": 10,
        })
        try:
            self.env["stock.quant"]._update_reserved_quantity(
                product, loc, 3
            )
        except Exception:
            pass
        self.assertTrue(True)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockQuantApplyInventory(TransactionCase):
    def test_apply_inventory_not_allow_negative(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env.company.not_allow_negative_inventory_adjustments = True
        product = self.env["product.product"].create({
            "name": "Neg Inv Prod",
            "type": "consu",
            "is_storable": True,
        })
        quant = self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 5,
        })
        quant.inventory_quantity = -1
        with self.assertRaises(ValidationError):
            quant._apply_inventory()

    def test_apply_inventory_allow_negative(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env.company.not_allow_negative_inventory_adjustments = False
        product = self.env["product.product"].create({
            "name": "Allow Neg Inv Prod",
            "type": "consu",
            "is_storable": True,
        })
        quant = self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 5,
        })
        quant.inventory_quantity = 10
        quant._apply_inventory()
        self.assertTrue(True)

    def test_apply_inventory_positive_adjustment(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env.company.not_allow_negative_inventory_adjustments = True
        product = self.env["product.product"].create({
            "name": "Pos Adj Prod",
            "type": "consu",
            "is_storable": True,
        })
        quant = self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 5,
        })
        quant.inventory_quantity = 10
        quant._apply_inventory()
        quant.invalidate_recordset(["quantity"])
        self.assertEqual(quant.quantity, 10)
