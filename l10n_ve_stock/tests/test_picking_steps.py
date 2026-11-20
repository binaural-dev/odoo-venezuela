from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestPickingSteps(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.partner = cls.env["res.partner"].create({"name": "Cliente pasos"})
        cls.warehouse = cls.env["stock.warehouse"].create(
            {"name": "Almacén 3 pasos", "code": "W3P", "delivery_steps": "pick_pack_ship"}
        )
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.product = cls.env["product.product"].create(
            {"name": "Producto pasos", "type": "product", "list_price": 10}
        )
        cls.env["stock.quant"]._update_available_quantity(cls.product, cls.warehouse.lot_stock_id, 50)

    def _procure(self, qty=5):
        group = self.env["procurement.group"].create({"name": "Grupo pasos", "partner_id": self.partner.id})
        self.env["procurement.group"].run(
            [
                self.env["procurement.group"].Procurement(
                    self.product,
                    qty,
                    self.product.uom_id,
                    self.customer_location,
                    "pasos",
                    "pasos",
                    self.company,
                    {"warehouse_id": self.warehouse, "group_id": group},
                )
            ]
        )
        pickings = self.env["stock.picking"].search([("group_id", "=", group.id)])
        return (
            pickings.filtered(lambda p: p.type_delivery_step == "pick"),
            pickings.filtered(lambda p: p.type_delivery_step == "pack"),
            pickings.filtered(lambda p: p.type_delivery_step == "out"),
        )

    def _user(self, login, *groups):
        return new_test_user(
            self.env,
            login=login,
            email=f"{login}@example.com",
            groups=",".join(("stock.group_stock_manager",) + groups),
        )

    def test_steps_counters_and_actions(self):
        pick, pack, out = self._procure()
        self.assertTrue(pick and pack and out)
        self.assertEqual(self.warehouse.pick_type_id._get_type_steps(), "pick")
        self.assertEqual(self.warehouse.pack_type_id._get_type_steps(), "pack")

        self.assertEqual((out.picks_count, out.packs_count, out.outs_count), (1, 1, 0))

        action = out.action_get_picks()
        self.assertEqual(action["res_id"], pick.id)
        self.assertEqual(action["context"]["default_type_delivery_step"], "pick")
        self.assertEqual(pick.action_get_packs()["res_id"], pack.id)
        self.assertEqual(pick.action_get_outs()["res_id"], out.id)
        with self.assertRaises(UserError):
            out.action_get_outs()

        self.assertEqual(out._get_picks(assigned=True), pick)
        self.assertEqual(pick._get_picks(assigned=True), pick)
        self.assertEqual(pack._get_packs(assigned=True), pack)
        self.assertEqual(out._get_outs(assigned=True), out)
        self.assertEqual(pick._get_packs(assigned=True), pack)
        self.assertEqual(pick._get_outs(assigned=True), out)

    def test_action_with_several_pickings_uses_domain(self):
        pick, _pack, out = self._procure()
        default = {"group_id": pick.group_id.id}
        if "transfer_reason_id" in pick._fields:
            default["transfer_reason_id"] = self.env["transfer.reason"].search([], limit=1).id
        second_pick = pick.copy(default)

        action = out.action_get_picks()

        self.assertEqual(set(action["domain"][0][2]), set((pick | second_pick).ids))

    def test_picking_without_group(self):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.int_type_id.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.warehouse.lot_stock_id.id,
            }
        )
        self.assertFalse(picking._get_picks() or picking._get_packs() or picking._get_outs())
        self.assertEqual(picking.type_delivery_step, "int")

    def test_batch_assign_with_mixed_steps(self):
        pick, _pack, out = self._procure()
        (pick | out).action_assign()
        self.assertEqual(pick.state, "assigned")

    def test_blocked_user_cannot_create_shipments(self):
        user = self._user("bloqueo_envios", "l10n_ve_stock.group_block_type_inventory_transfers_expeditions")
        with self.assertRaises(UserError):
            self.env["stock.picking"].with_user(user).create(
                {
                    "picking_type_id": self.warehouse.out_type_id.id,
                    "location_id": self.warehouse.wh_output_stock_loc_id.id,
                    "location_dest_id": self.customer_location.id,
                }
            )

        internal = self.env["stock.picking"].with_user(user).create(
            {
                "picking_type_id": self.warehouse.int_type_id.id,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.warehouse.lot_stock_id.id,
            }
        )
        self.assertTrue(internal)

    def test_blocked_user_cannot_change_shipment_lines(self):
        _pick, _pack, out = self._procure()
        user = self._user("bloqueo_lineas", "l10n_ve_stock.group_block_type_inventory_transfers_expeditions")
        out_user = out.with_user(user)
        move = out.move_ids

        with self.assertRaises(UserError):
            out_user.write(
                {
                    "move_ids_without_package": [
                        (
                            0,
                            "virtual_1",
                            {
                                "name": self.product.name,
                                "product_id": self.product.id,
                                "product_uom_qty": 1,
                                "product_uom": self.product.uom_id.id,
                                "location_id": out.location_id.id,
                                "location_dest_id": out.location_dest_id.id,
                            },
                        )
                    ]
                }
            )
        with self.assertRaises(UserError):
            out_user.write({"move_ids_without_package": [(1, move.id, {})]})
        with self.assertRaises(UserError):
            out_user.write({"move_ids_without_package": [(1, move.id, {"quantity": 99})]})

        out_user.write({"move_ids_without_package": [(1, move.id, {"quantity": 1})]})
        self.assertEqual(move.quantity, 1)

    def test_barcode_fields_include_priority(self):
        if "stock_barcode" not in self.env["ir.module.module"]._installed():
            self.skipTest("stock_barcode no está instalado")
        self.assertIn("priority_location", self.env["stock.move.line"]._get_fields_stock_barcode())

    def test_negative_stock_movement_is_blocked(self):
        self.company.not_allow_negative_stock_movement = True
        shelf = self.env["stock.location"].create(
            {"name": "Estante vacío", "usage": "internal", "location_id": self.warehouse.lot_stock_id.id}
        )
        internal = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.int_type_id.id,
                "location_id": shelf.id,
                "location_dest_id": self.warehouse.lot_stock_id.id,
                "move_ids": [
                    (0, 0, {
                        "name": self.product.name,
                        "product_id": self.product.id,
                        "product_uom_qty": 2,
                        "product_uom": self.product.uom_id.id,
                        "location_id": shelf.id,
                        "location_dest_id": self.warehouse.lot_stock_id.id,
                    })
                ],
            }
        )
        internal.action_confirm()
        internal.move_ids.quantity = 2
        with self.assertRaises(ValidationError):
            internal.button_validate()

        self.env["stock.quant"]._update_available_quantity(self.product, shelf, 5)
        internal.move_ids.quantity = 2
        internal.button_validate()
        self.assertEqual(internal.state, "done")
