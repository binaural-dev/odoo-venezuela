from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestAlterLocationMoves(TransactionCase):
    """Alternate locations ledger kept in sync by validated moves."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.use_alternate_locations = True
        cls.warehouse = cls.env["stock.warehouse"].create(
            {"name": "Alter Moves Warehouse", "code": "AMW", "delivery_steps": "pick_ship"}
        )
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.output_location = cls.warehouse.wh_output_stock_loc_id
        cls.shelf = cls.env["stock.location"].create(
            {"name": "Shelf", "location_id": cls.stock_location.id, "usage": "internal"}
        )
        cls.orphan_location = cls.env["stock.location"].create(
            {"name": "Orphan Shelf", "usage": "internal"}
        )
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.product = cls._create_product("Alter Moves Product")
        cls.alter = cls.env["stock.picking.alter.location"].create(
            {
                "product_id": cls.product.id,
                "pick_location": cls.stock_location.id,
                "stock_alter_location_lines": [
                    (0, 0, {"location_id": cls.stock_location.id, "available_qty": 10.0})
                ],
            }
        )

    @classmethod
    def _create_product(cls, name, storable=True):
        return cls.env["product.product"].create(
            {"name": name, "type": "consu", "is_storable": storable}
        )

    def _done_picking(self, picking_type, source, destination, product=None, qty=3.0):
        product = product or self.product
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": picking_type.id,
                "location_id": source.id,
                "location_dest_id": destination.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "product_uom": product.uom_id.id,
                            "location_id": source.id,
                            "location_dest_id": destination.id,
                        },
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        picking.move_ids.quantity = qty
        picking.move_ids.picked = True
        picking.button_validate()
        return picking

    def _qty(self, location):
        return sum(self.alter.get_line(location).mapped("available_qty"))

    # stock.move: pick and delivery through Output

    def test_pick_and_delivery_update_output_line(self):
        self.env["stock.quant"]._update_available_quantity(self.product, self.stock_location, 10.0)
        self._done_picking(
            self.warehouse.pick_type_id, self.stock_location, self.output_location
        )
        self.assertEqual(self._qty(self.output_location), 3.0)
        self.assertEqual(self._qty(self.stock_location), 7.0)

        self._done_picking(
            self.warehouse.out_type_id, self.output_location, self.customer_location, qty=2.0
        )
        self.assertEqual(self._qty(self.output_location), 1.0)

    def test_internal_move_does_not_touch_ledger(self):
        self.env["stock.quant"]._update_available_quantity(self.product, self.stock_location, 10.0)
        self._done_picking(self.warehouse.int_type_id, self.stock_location, self.shelf)
        self.assertEqual(self._qty(self.stock_location), 10.0)
        self.assertFalse(self.alter.get_line(self.shelf))

    def test_moves_skipped_by_ledger_hook(self):
        consumable = self._create_product("Not Storable", storable=False)
        without_alter = self._create_product("Without Alter Record")
        moves = self.env["stock.move"].create(
            [
                {
                    "product_id": product.id,
                    "product_uom_qty": 1.0,
                    "product_uom": product.uom_id.id,
                    "location_id": source.id,
                    "location_dest_id": destination.id,
                }
                for product, source, destination in (
                    (consumable, self.stock_location, self.output_location),
                    (without_alter, self.stock_location, self.output_location),
                    (self.product, self.orphan_location, self.customer_location),
                    (self.product, self.stock_location, self.output_location),
                )
            ]
        )
        moves._update_alter_location_on_move_done()
        self.assertEqual(self._qty(self.stock_location), 10.0)
        self.assertFalse(self.alter.get_line(self.output_location))

    def test_get_warehouse_from_move_without_picking(self):
        move = self.env["stock.move"].create(
            {
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
                "product_uom": self.product.uom_id.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.shelf.id,
            }
        )
        self.assertEqual(self.env["stock.move"]._get_warehouse_from_move(move), self.warehouse)

    # stock.picking: receipts

    def test_receipt_increments_pick_location(self):
        self._done_picking(self.warehouse.in_type_id, self.supplier_location, self.stock_location)
        self.assertEqual(self._qty(self.stock_location), 13.0)

    def test_receipt_into_child_location_finds_warehouse(self):
        self._done_picking(self.warehouse.in_type_id, self.supplier_location, self.shelf)
        self.assertEqual(self._qty(self.stock_location), 13.0)

    def test_receipt_skips_unrelated_lines(self):
        consumable = self._create_product("Receipt Not Storable", storable=False)
        without_alter = self._create_product("Receipt Without Alter")
        self._done_picking(
            self.warehouse.in_type_id, self.supplier_location, self.stock_location, consumable
        )
        self._done_picking(
            self.warehouse.in_type_id, self.supplier_location, self.stock_location, without_alter
        )
        self._done_picking(
            self.warehouse.in_type_id, self.supplier_location, self.orphan_location
        )
        self.alter.pick_location = False
        self._done_picking(self.warehouse.in_type_id, self.supplier_location, self.stock_location)
        self.assertEqual(self._qty(self.stock_location), 10.0)

    def test_receipt_hook_skips_zero_quantity_lines(self):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.in_type_id.id,
                "location_id": self.supplier_location.id,
                "location_dest_id": self.stock_location.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 2.0,
                            "product_uom": self.product.uom_id.id,
                            "location_id": self.supplier_location.id,
                            "location_dest_id": self.stock_location.id,
                        },
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.move_ids.quantity = 2.0
        picking.move_line_ids.quantity = 0.0
        picking._update_alter_location_lines_on_receive()
        self.assertEqual(self._qty(self.stock_location), 10.0)

    def test_receive_hook_ignores_non_incoming(self):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.int_type_id.id,
                "location_id": self.stock_location.id,
                "location_dest_id": self.shelf.id,
            }
        )
        self.assertIsNone(picking._update_alter_location_lines_on_receive())
