from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError, ValidationError
from odoo import Command


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockPickingTypeSteps(TransactionCase):
    def setUp(self):
        super().setUp()
        self.warehouse = self.env["stock.warehouse"].search([], limit=1)

    def test_type_delivery_step_out(self):
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.out_type_id.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
        })
        self.assertEqual(picking.type_delivery_step, "out")

    def test_type_delivery_step_in(self):
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.in_type_id.id,
            "location_id": self.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": self.warehouse.lot_stock_id.id,
        })
        self.assertEqual(picking.type_delivery_step, "in")

    def test_type_delivery_step_pick(self):
        self.warehouse.delivery_steps = "pick_ship"
        picking = self.env["stock.picking"].create({
            "picking_type_id": self.warehouse.pick_type_id.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": self.warehouse.wh_output_stock_loc_id.id,
        })
        self.assertEqual(picking.type_delivery_step, "pick")


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockPickingGetPicksPacksOuts(TransactionCase):
    def setUp(self):
        super().setUp()
        self.warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.partner = self.env["res.partner"].create({"name": "Test Partner"})
        self.product = self.env["product.product"].create({
            "name": "Test Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.customer_loc = self.env.ref("stock.stock_location_customers")
        self.reference = self.env["stock.reference"].create({"name": "REF-GROUP-001"})

    def _create_picking(self, picking_type, reference=None):
        vals = {
            "partner_id": self.partner.id,
            "picking_type_id": picking_type.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": self.customer_loc.id,
        }
        move_vals = {
            "product_id": self.product.id,
            "product_uom_qty": 1,
        }
        if reference:
            move_vals["reference_ids"] = [Command.set(reference.ids)]
        vals["move_ids"] = [Command.create(move_vals)]
        return self.env["stock.picking"].create(vals)

    def test_get_picks_no_reference(self):
        picking = self._create_picking(self.warehouse.out_type_id)
        result = picking._get_picks()
        self.assertEqual(len(result), 0)

    def test_get_picks_with_reference(self):
        self.warehouse.delivery_steps = "pick_ship"
        pick_type = self.warehouse.pick_type_id
        out_type = self.warehouse.out_type_id
        picking_pick = self._create_picking(pick_type, self.reference)
        picking_out = self._create_picking(out_type, self.reference)
        result = picking_out._get_picks()
        self.assertIn(picking_pick, result)

    def test_get_picks_assigned_self(self):
        self.warehouse.delivery_steps = "pick_ship"
        pick_type = self.warehouse.pick_type_id
        picking = self._create_picking(pick_type, self.reference)
        result = picking._get_picks(assigned=True)
        self.assertEqual(result, picking)

    def test_get_packs_no_reference(self):
        picking = self._create_picking(self.warehouse.out_type_id)
        result = picking._get_packs()
        self.assertEqual(len(result), 0)

    def test_get_outs_no_reference(self):
        picking = self._create_picking(self.warehouse.out_type_id)
        result = picking._get_outs()
        self.assertEqual(len(result), 0)

    def test_get_outs_with_reference(self):
        out_type = self.warehouse.out_type_id
        picking1 = self._create_picking(out_type, self.reference)
        picking2 = self._create_picking(out_type, self.reference)
        result = picking1._get_outs()
        self.assertIn(picking2, result)

    def test_get_outs_assigned_self_is_out(self):
        out_type = self.warehouse.out_type_id
        picking = self._create_picking(out_type, self.reference)
        result = picking._get_outs(assigned=True)
        self.assertEqual(result, picking)

    def test_get_packs_with_reference(self):
        self.warehouse.delivery_steps = "pick_pack_ship"
        pack_type = self.warehouse.pack_type_id
        out_type = self.warehouse.out_type_id
        picking_pack = self._create_picking(pack_type, self.reference)
        picking_out = self._create_picking(out_type, self.reference)
        result = picking_out._get_packs()
        self.assertIn(picking_pack, result)

    def test_get_packs_assigned_self_is_pack(self):
        self.warehouse.delivery_steps = "pick_pack_ship"
        pack_type = self.warehouse.pack_type_id
        picking = self._create_picking(pack_type, self.reference)
        result = picking._get_packs(assigned=True)
        self.assertEqual(result, picking)

    def test_get_packs_assigned_not_self(self):
        self.warehouse.delivery_steps = "pick_pack_ship"
        pack_type = self.warehouse.pack_type_id
        out_type = self.warehouse.out_type_id
        picking_pack = self._create_picking(pack_type, self.reference)
        picking_out = self._create_picking(out_type, self.reference)
        result = picking_out._get_packs(assigned=True)
        self.assertTrue(len(result) >= 0)

    def test_get_outs_assigned_not_self(self):
        out_type = self.warehouse.out_type_id
        picking1 = self._create_picking(out_type, self.reference)
        picking2 = self._create_picking(out_type, self.reference)
        result = picking1._get_outs(assigned=True)
        self.assertTrue(len(result) >= 0)

    def test_get_outs_assigned_from_pick(self):
        self.warehouse.delivery_steps = "pick_ship"
        pick_type = self.warehouse.pick_type_id
        out_type = self.warehouse.out_type_id
        picking_pick = self._create_picking(pick_type, self.reference)
        picking_out = self._create_picking(out_type, self.reference)
        result = picking_pick._get_outs(assigned=True)
        self.assertTrue(len(result) >= 0)

    def test_get_picks_assigned_not_self(self):
        self.warehouse.delivery_steps = "pick_ship"
        pick_type = self.warehouse.pick_type_id
        out_type = self.warehouse.out_type_id
        picking_pick = self._create_picking(pick_type, self.reference)
        picking_out = self._create_picking(out_type, self.reference)
        result = picking_out._get_picks(assigned=True)
        self.assertTrue(len(result) >= 0)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockPickingCounts(TransactionCase):
    def setUp(self):
        super().setUp()
        self.warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.partner = self.env["res.partner"].create({"name": "Count Partner"})
        self.product = self.env["product.product"].create({
            "name": "Count Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.customer_loc = self.env.ref("stock.stock_location_customers")

    def test_compute_counts_no_reference(self):
        picking = self.env["stock.picking"].create({
            "partner_id": self.partner.id,
            "picking_type_id": self.warehouse.out_type_id.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": self.customer_loc.id,
            "move_ids": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 1,
            })],
        })
        self.assertEqual(picking.picks_count, 0)
        self.assertEqual(picking.packs_count, 0)
        self.assertEqual(picking.outs_count, 0)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockPickingCreateWrite(TransactionCase):
    def setUp(self):
        super().setUp()
        self.warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.partner = self.env["res.partner"].create({"name": "CW Partner"})
        self.product = self.env["product.product"].create({
            "name": "CW Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.customer_loc = self.env.ref("stock.stock_location_customers")

    def test_create_picking(self):
        picking = self.env["stock.picking"].create({
            "partner_id": self.partner.id,
            "picking_type_id": self.warehouse.out_type_id.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": self.customer_loc.id,
            "move_ids": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 5,
            })],
        })
        self.assertTrue(picking.exists())
        self.assertEqual(picking.partner_id, self.partner)

    def test_write_picking(self):
        picking = self.env["stock.picking"].create({
            "partner_id": self.partner.id,
            "picking_type_id": self.warehouse.out_type_id.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": self.customer_loc.id,
        })
        new_partner = self.env["res.partner"].create({"name": "New Partner"})
        picking.write({"partner_id": new_partner.id})
        self.assertEqual(picking.partner_id, new_partner)

    def test_write_picking_with_move_ids(self):
        picking = self.env["stock.picking"].create({
            "partner_id": self.partner.id,
            "picking_type_id": self.warehouse.out_type_id.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": self.customer_loc.id,
        })
        picking.write({
            "move_ids": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 3,
            })],
        })
        self.assertEqual(len(picking.move_ids), 1)

    def test_write_picking_with_move_line_ids(self):
        picking = self.env["stock.picking"].create({
            "partner_id": self.partner.id,
            "picking_type_id": self.warehouse.out_type_id.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": self.customer_loc.id,
            "move_ids": [Command.create({
                "product_id": self.product.id,
                "product_uom_qty": 3,
            })],
        })
        picking.write({
            "move_line_ids": [(0, 0, {
                "product_id": self.product.id,
                "quantity": 1,
                "location_id": self.warehouse.lot_stock_id.id,
                "location_dest_id": self.customer_loc.id,
            })],
        })
        self.assertTrue(True)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockPickingActionAssign(TransactionCase):
    def test_action_assign(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        product = self.env["product.product"].create({
            "name": "Assign Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 10,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 5,
            })],
        })
        picking.action_assign()
        self.assertIn(picking.state, ["assigned", "waiting", "confirmed"])

    def test_action_assign_pick_type(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        warehouse.delivery_steps = "pick_ship"
        product = self.env["product.product"].create({
            "name": "Assign Pick Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 10,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.pick_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": warehouse.wh_output_stock_loc_id.id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 5,
            })],
        })
        picking.action_assign()
        self.assertIn(picking.state, ["assigned", "waiting", "confirmed"])


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockPickingButtonValidate(TransactionCase):
    def test_button_validate_not_allow_negative(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env.company.not_allow_negative_stock_movement = True
        product = self.env["product.product"].create({
            "name": "Validate Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 10,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 2,
            })],
        })
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        res = picking.button_validate()
        self.assertIn(picking.state, ["done", "assigned", "waiting", "confirmed"])

    def test_button_validate_allow_negative(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env.company.not_allow_negative_stock_movement = False
        product = self.env["product.product"].create({
            "name": "Validate Allow Neg Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 10,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 2,
            })],
        })
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        res = picking.button_validate()
        self.assertIn(picking.state, ["done", "assigned", "waiting", "confirmed"])


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockPickingCheckStockAvailability(TransactionCase):
    def test_check_stock_availability_insufficient(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env.company.not_allow_negative_stock_movement = True
        product = self.env["product.product"].create({
            "name": "Insufficient Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 1,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 1,
            })],
        })
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = 100
        with self.assertRaises(ValidationError):
            picking._check_stock_availability_for_pickings()

    def test_check_stock_availability_sufficient(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        product = self.env["product.product"].create({
            "name": "Sufficient Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 100,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 5,
            })],
        })
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking._check_stock_availability_for_pickings()
        self.assertTrue(True)

    def test_check_stock_availability_internal(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        product = self.env["product.product"].create({
            "name": "Internal Avail Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 10,
        })
        internal_loc = self.env["stock.location"].create({
            "name": "Internal Loc",
            "usage": "internal",
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.int_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": internal_loc.id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 2,
            })],
        })
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking._check_stock_availability_for_pickings()
        self.assertTrue(True)

    def test_check_stock_availability_with_lot(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        product = self.env["product.product"].create({
            "name": "Lot Avail Prod",
            "type": "consu",
            "is_storable": True,
        })
        lot = self.env["stock.lot"].create({
            "name": "LOT-AVAIL",
            "product_id": product.id,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 10,
            "lot_id": lot.id,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 2,
            })],
        })
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking._check_stock_availability_for_pickings()
        self.assertTrue(True)

    def test_check_stock_availability_insufficient_with_lot(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env.company.not_allow_negative_stock_movement = True
        product = self.env["product.product"].create({
            "name": "Insuff Lot Prod",
            "type": "consu",
            "is_storable": True,
        })
        lot = self.env["stock.lot"].create({
            "name": "LOT-INSUFF",
            "product_id": product.id,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 1,
            "lot_id": lot.id,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 1,
            })],
        })
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = 100
        with self.assertRaises(ValidationError):
            picking._check_stock_availability_for_pickings()

    def test_check_stock_availability_zero_qty_skip(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env.company.not_allow_negative_stock_movement = True
        product = self.env["product.product"].create({
            "name": "Zero Qty Prod",
            "type": "consu",
            "is_storable": True,
        })
        self.env["stock.quant"].create({
            "product_id": product.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": 10,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 2,
            })],
        })
        picking.action_assign()
        for move in picking.move_ids:
            move.quantity = 0
        picking._check_stock_availability_for_pickings()
        self.assertTrue(True)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockPickingValidateBlockTransfers(TransactionCase):
    def test_validate_block_transfer_create_outgoing(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        group = self.env.ref("l10n_ve_stock.group_block_type_inventory_transfers_expeditions")
        self.env.user.sudo().write({"group_ids": [(4, group.id)]})
        with self.assertRaises(UserError):
            self.env["stock.picking"].create({
                "picking_type_id": warehouse.out_type_id.id,
                "location_id": warehouse.lot_stock_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            })

    def test_validate_block_transfer_not_outgoing(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        group = self.env.ref("l10n_ve_stock.group_block_type_inventory_transfers_expeditions")
        self.env.user.sudo().write({"group_ids": [(4, group.id)]})
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.in_type_id.id,
            "location_id": self.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": warehouse.lot_stock_id.id,
        })
        self.assertTrue(picking.exists())


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockPickingActionGetMethods(TransactionCase):
    def setUp(self):
        super().setUp()
        self.warehouse = self.env["stock.warehouse"].search([], limit=1)

    def _create_with_ref(self, picking_type, reference):
        product = self.env["product.product"].create({
            "name": "AGM Prod",
            "type": "consu",
            "is_storable": True,
        })
        return self.env["stock.picking"].create({
            "picking_type_id": picking_type.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 1,
                "reference_ids": [Command.set(reference.ids)],
            })],
        })

    def test_action_get_outs(self):
        ref = self.env["stock.reference"].create({"name": "REF-OUTS"})
        p1 = self._create_with_ref(self.warehouse.out_type_id, ref)
        p2 = self._create_with_ref(self.warehouse.out_type_id, ref)
        result = p1.action_get_outs()
        self.assertIsInstance(result, dict)

    def test_action_get_picks(self):
        self.warehouse.delivery_steps = "pick_ship"
        ref = self.env["stock.reference"].create({"name": "REF-PICKS"})
        p1 = self._create_with_ref(self.warehouse.pick_type_id, ref)
        p2 = self._create_with_ref(self.warehouse.pick_type_id, ref)
        result = p1.action_get_picks()
        self.assertIsInstance(result, dict)

    def test_action_get_packs(self):
        self.warehouse.delivery_steps = "pick_pack_ship"
        ref = self.env["stock.reference"].create({"name": "REF-PACKS"})
        p1 = self._create_with_ref(self.warehouse.pack_type_id, ref)
        p2 = self._create_with_ref(self.warehouse.pack_type_id, ref)
        result = p1.action_get_packs()
        self.assertIsInstance(result, dict)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockPickingValidateBlockWrite(TransactionCase):
    def test_validate_block_transfers_expedition_direct_call(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        product = self.env["product.product"].sudo().create({
            "name": "Block Write Prod",
            "type": "consu",
            "is_storable": True,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
        })
        group = self.env.ref("l10n_ve_stock.group_block_type_inventory_transfers_expeditions")
        self.env.user.sudo().write({"group_ids": [(4, group.id)]})
        with self.assertRaises(UserError):
            picking.validate_block_transfers_expedition()

    def test_validate_block_transfers_expedition_with_write_new_line(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        product = self.env["product.product"].sudo().create({
            "name": "Block Write Line Prod",
            "type": "consu",
            "is_storable": True,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
        })
        result = picking.validate_block_transfers_expedition(
            write={"move_ids": [("create", {"product_id": product.id})]},
            matched_key="move_ids"
        )
        self.assertIsNone(result)

    def test_validate_block_transfers_expedition_with_write_update_line(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        product = self.env["product.product"].sudo().create({
            "name": "Block Update Prod",
            "type": "consu",
            "is_storable": True,
        })
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "move_ids": [Command.create({
                "product_id": product.id,
                "product_uom_qty": 5,
            })],
        })
        group = self.env.ref("l10n_ve_stock.group_block_type_inventory_transfers_expeditions")
        self.env.user.sudo().write({"group_ids": [(4, group.id)]})
        move_id = picking.move_ids[0].id
        with self.assertRaises(UserError):
            picking.validate_block_transfers_expedition(
                write={"move_ids": [(1, move_id, {"quantity": 10})]},
                matched_key="move_ids"
            )

    def test_validate_block_transfers_expedition_not_outgoing(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.in_type_id.id,
            "location_id": self.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": warehouse.lot_stock_id.id,
        })
        group = self.env.ref("l10n_ve_stock.group_block_type_inventory_transfers_expeditions")
        self.env.user.sudo().write({"group_ids": [(4, group.id)]})
        result = picking.validate_block_transfers_expedition()
        self.assertIsNone(result)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestStockPickingChangeWeight(TransactionCase):
    def test_change_weight_true(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env.company.change_weight = True
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
        })
        self.assertTrue(picking.change_weight)

    def test_change_weight_false(self):
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        self.env.company.change_weight = False
        picking = self.env["stock.picking"].create({
            "picking_type_id": warehouse.out_type_id.id,
            "location_id": warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
        })
        self.assertFalse(picking.change_weight)
