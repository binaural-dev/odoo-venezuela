from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockWarehouse(TransactionCase):
    def test_get_picking_type_create_values(self):
        warehouse = self.env["stock.warehouse"].create({
            "name": "Test WH PickingType",
            "code": "TWHP",
        })
        self.assertTrue(warehouse.exists())
        self.assertTrue(warehouse.in_type_id)
        self.assertTrue(warehouse.out_type_id)

    def test_warehouse_inherits(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        result = warehouse._get_picking_type_create_values(100)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, tuple)

    def test_physical_address_field(self):
        warehouse = self.env["stock.warehouse"].create({
            "name": "Test WH Physical Address",
            "code": "TWPA",
            "physical_address": "Av. Principal, Zona Industrial, Caracas",
        })
        self.assertEqual(
            warehouse.physical_address, "Av. Principal, Zona Industrial, Caracas"
        )