from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockPickingTypeSteps(TransactionCase):
    def setUp(self):
        super().setUp()
        self.warehouse = self.env["stock.warehouse"].search([], limit=1)

    def test_type_steps_in(self):
        self.assertEqual(self.warehouse.in_type_id.type_steps, "in")

    def test_type_steps_out(self):
        self.assertEqual(self.warehouse.out_type_id.type_steps, "out")

    def test_type_steps_int(self):
        int_type = self.warehouse.int_type_id
        if int_type:
            self.assertEqual(int_type.type_steps, "int")

    def test_type_steps_pick(self):
        self.warehouse.delivery_steps = "pick_ship"
        self.assertEqual(self.warehouse.pick_type_id.type_steps, "pick")

    def test_type_steps_pack(self):
        self.warehouse.delivery_steps = "pick_pack_ship"
        self.assertEqual(self.warehouse.pack_type_id.type_steps, "pack")

    def test_get_type_steps_returns_false_for_unmatched(self):
        custom_type = self.env["stock.picking.type"].create({
            "name": "Custom Type",
            "code": "internal",
            "sequence_code": "CUSTOM",
            "warehouse_id": self.warehouse.id,
        })
        result = custom_type._get_type_steps()
        self.assertFalse(result)

    def test_compute_type_steps_in(self):
        self.warehouse.in_type_id._compute_type_steps()
        self.assertEqual(self.warehouse.in_type_id.type_steps, "in")

    def test_compute_type_steps_out(self):
        self.warehouse.out_type_id._compute_type_steps()
        self.assertEqual(self.warehouse.out_type_id.type_steps, "out")

    def test_compute_type_steps_int(self):
        int_type = self.warehouse.int_type_id
        if int_type:
            int_type._compute_type_steps()
            self.assertEqual(int_type.type_steps, "int")

    def test_compute_type_steps_pick(self):
        self.warehouse.delivery_steps = "pick_ship"
        self.warehouse.pick_type_id._compute_type_steps()
        self.assertEqual(self.warehouse.pick_type_id.type_steps, "pick")

    def test_compute_type_steps_pack(self):
        self.warehouse.delivery_steps = "pick_pack_ship"
        self.warehouse.pack_type_id._compute_type_steps()
        self.assertEqual(self.warehouse.pack_type_id.type_steps, "pack")

    def test_get_type_steps_in(self):
        self.assertEqual(self.warehouse.in_type_id._get_type_steps(), "in")

    def test_get_type_steps_out(self):
        self.assertEqual(self.warehouse.out_type_id._get_type_steps(), "out")

    def test_get_type_steps_int(self):
        int_type = self.warehouse.int_type_id
        if int_type:
            self.assertEqual(int_type._get_type_steps(), "int")

    def test_get_type_steps_pick(self):
        self.warehouse.delivery_steps = "pick_ship"
        self.assertEqual(self.warehouse.pick_type_id._get_type_steps(), "pick")

    def test_get_type_steps_pack(self):
        self.warehouse.delivery_steps = "pick_pack_ship"
        self.assertEqual(self.warehouse.pack_type_id._get_type_steps(), "pack")
