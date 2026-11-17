from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


class AlterLocationCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.use_alternate_locations = True
        cls.warehouse = cls.env["stock.warehouse"].create(
            {"name": "Alter Actions Warehouse", "code": "AAW"}
        )
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.output_location = cls.warehouse.wh_output_stock_loc_id
        cls.location_a = cls.env["stock.location"].create(
            {"name": "Shelf A", "location_id": cls.stock_location.id, "usage": "internal"}
        )
        cls.location_b = cls.env["stock.location"].create(
            {"name": "Shelf B", "location_id": cls.stock_location.id, "usage": "internal"}
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Alter Actions Product", "type": "consu", "is_storable": True}
        )

    def _create_alter(self, lines=None, **vals):
        values = {
            "product_id": self.product.id,
            "pick_location": self.stock_location.id,
            "stock_alter_location_lines": [
                (0, 0, {"location_id": location.id, "available_qty": qty})
                for location, qty in (lines or [])
            ],
        }
        values.update(vals)
        return self.env["stock.picking.alter.location"].create(values)

    def _qty(self, alter, location):
        return sum(alter.get_line(location).mapped("available_qty"))


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestAlterLocationComputes(AlterLocationCommon):
    def test_warehouse_and_company_from_pick_location(self):
        alter = self._create_alter()
        self.assertEqual(alter.warehouse_id, self.warehouse)
        self.assertEqual(alter.company_id, self.warehouse.company_id)

    def test_warehouse_found_from_child_location(self):
        alter = self._create_alter(pick_location=self.location_a.id)
        self.assertEqual(alter.warehouse_id, self.warehouse)

    def test_without_pick_location_has_no_warehouse(self):
        alter = self._create_alter(pick_location=False)
        self.assertFalse(alter.warehouse_id)
        self.assertEqual(alter.company_id, self.env.company)

    def test_pick_location_outside_warehouses_has_no_warehouse(self):
        orphan = self.env["stock.location"].create({"name": "Orphan", "usage": "internal"})
        alter = self._create_alter(pick_location=orphan.id)
        self.assertFalse(alter.warehouse_id)

    def test_quantities_split_between_pick_output_and_others(self):
        alter = self._create_alter(
            lines=[
                (self.stock_location, 10.0),
                (self.location_a, 4.0),
                (self.output_location, 3.0),
            ]
        )
        self.assertEqual(alter.pick_quantity, 10.0)
        self.assertEqual(alter.total_alter_quantity, 14.0)
        self.assertEqual(alter.total_quantity, 4.0)

    def test_quantities_without_warehouse(self):
        alter = self._create_alter(
            pick_location=False,
            lines=[(self.location_a, 4.0), (self.output_location, 3.0)],
        )
        self.assertEqual(alter.pick_quantity, 0.0)
        self.assertEqual(alter.total_alter_quantity, 7.0)
        self.assertEqual(alter.total_quantity, 7.0)

    def test_check_location_in_lines_and_get_line(self):
        alter = self._create_alter(lines=[(self.location_a, 4.0)])
        self.assertTrue(alter.check_location_in_lines(self.location_a))
        self.assertFalse(alter.check_location_in_lines(self.location_b))
        self.assertEqual(alter.get_line(self.location_a).available_qty, 4.0)
        self.assertFalse(alter.get_line(self.location_b))


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestAlterLocationChangeQuantitiesAction(AlterLocationCommon):
    def test_action_with_pick_location(self):
        alter = self._create_alter(lines=[(self.location_a, 4.0)])
        action = alter.action_change_product_quantities()
        self.assertEqual(action["res_model"], "move.alter.location.qtities.wizard")
        self.assertEqual(action["context"]["default_to_location"], self.stock_location.id)
        self.assertEqual(
            action["context"]["domain_locations"],
            [self.location_a.id, self.stock_location.id],
        )

    def test_action_without_pick_location(self):
        alter = self._create_alter(pick_location=False, lines=[(self.location_a, 4.0)])
        action = alter.action_change_product_quantities()
        self.assertEqual(action["context"]["domain_locations"], [self.location_a.id])


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestAlterLocationInternalTransfer(AlterLocationCommon):
    def test_transfer_without_source_line_raises(self):
        alter = self._create_alter()
        with self.assertRaises(UserError):
            alter.action_internal_transfer(self.location_a.id, self.location_b.id, 1.0)

    def test_transfer_more_than_available_raises(self):
        alter = self._create_alter(lines=[(self.location_a, 2.0)])
        with self.assertRaises(UserError):
            alter.action_internal_transfer(self.location_a.id, self.location_b.id, 5.0)

    def test_transfer_to_pick_location_over_maximum_raises(self):
        alter = self._create_alter(
            lines=[(self.location_a, 5.0), (self.stock_location, 8.0)],
            max_quantity=10.0,
        )
        with self.assertRaises(UserError):
            alter.action_internal_transfer(self.location_a.id, self.stock_location.id, 5.0)

    def test_transfer_from_pick_location_under_minimum_raises(self):
        alter = self._create_alter(
            lines=[(self.stock_location, 5.0)],
            min_quantity=3.0,
        )
        with self.assertRaises(UserError):
            alter.action_internal_transfer(self.stock_location.id, self.location_a.id, 4.0)

    def test_transfer_to_new_location_creates_line(self):
        alter = self._create_alter(lines=[(self.location_a, 5.0)])
        alter.action_internal_transfer(self.location_a.id, self.location_b.id, 2.0)
        self.assertEqual(self._qty(alter, self.location_a), 3.0)
        self.assertEqual(self._qty(alter, self.location_b), 2.0)

    def test_transfer_all_to_existing_line_removes_source(self):
        alter = self._create_alter(
            lines=[(self.location_a, 5.0), (self.stock_location, 1.0)],
            max_quantity=10.0,
            min_quantity=1.0,
        )
        alter.action_internal_transfer(self.location_a.id, self.stock_location.id, 5.0)
        self.assertFalse(alter.get_line(self.location_a))
        self.assertEqual(self._qty(alter, self.stock_location), 6.0)

    def test_transfer_from_pick_location_within_minimum(self):
        alter = self._create_alter(
            lines=[(self.stock_location, 5.0)],
            min_quantity=1.0,
        )
        alter.action_internal_transfer(self.stock_location.id, self.location_a.id, 2.0)
        self.assertEqual(self._qty(alter, self.stock_location), 3.0)

    def test_transfer_that_zeroes_destination_removes_it(self):
        alter = self._create_alter(lines=[(self.location_a, 2.0), (self.location_b, -2.0)])
        alter.action_internal_transfer(self.location_a.id, self.location_b.id, 2.0)
        self.assertFalse(alter.get_line(self.location_a))
        self.assertFalse(alter.get_line(self.location_b))


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestAlterLocationLedgerActions(AlterLocationCommon):
    def test_receive_quantity_existing_and_new_line(self):
        alter = self._create_alter(lines=[(self.location_a, 2.0)])
        alter.action_receive_quantity(self.location_a.id, 3.0)
        alter.action_receive_quantity(self.location_b.id, 4.0)
        self.assertEqual(self._qty(alter, self.location_a), 5.0)
        self.assertEqual(self._qty(alter, self.location_b), 4.0)

    def test_receive_quantity_to_zero_removes_line(self):
        alter = self._create_alter(lines=[(self.location_a, 2.0)])
        alter.action_receive_quantity(self.location_a.id, -2.0)
        self.assertFalse(alter.get_line(self.location_a))

    def test_move_to_output_creates_output_and_negative_source(self):
        alter = self._create_alter()
        alter.action_move_to_output(self.output_location.id, 3.0, self.stock_location.id)
        self.assertEqual(self._qty(alter, self.output_location), 3.0)
        self.assertEqual(self._qty(alter, self.stock_location), -3.0)

    def test_move_to_output_updates_existing_lines(self):
        alter = self._create_alter(
            lines=[(self.output_location, 1.0), (self.stock_location, 3.0)]
        )
        alter.action_move_to_output(self.output_location.id, 3.0, self.stock_location.id)
        self.assertEqual(self._qty(alter, self.output_location), 4.0)
        self.assertFalse(alter.get_line(self.stock_location))

    def test_move_to_output_that_zeroes_output_removes_it(self):
        alter = self._create_alter(
            lines=[(self.output_location, -2.0), (self.stock_location, 5.0)]
        )
        alter.action_move_to_output(self.output_location.id, 2.0, self.stock_location.id)
        self.assertFalse(alter.get_line(self.output_location))
        self.assertEqual(self._qty(alter, self.stock_location), 3.0)

    def test_deliver_from_output(self):
        alter = self._create_alter(lines=[(self.output_location, 5.0)])
        alter.action_deliver_from_output(self.output_location.id, 2.0)
        self.assertEqual(self._qty(alter, self.output_location), 3.0)
        alter.action_deliver_from_output(self.output_location.id, 3.0)
        self.assertFalse(alter.get_line(self.output_location))

    def test_deliver_from_output_without_line_does_nothing(self):
        alter = self._create_alter()
        alter.action_deliver_from_output(self.output_location.id, 2.0)
        self.assertFalse(alter.stock_alter_location_lines)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestAlterLocationSubtractPhysicalQuantity(AlterLocationCommon):
    def test_disabled_company_does_nothing(self):
        self.env.company.use_alternate_locations = False
        alter = self._create_alter(lines=[(self.stock_location, 5.0)])
        alter.subtract_physical_quantity()
        self.assertEqual(self._qty(alter, self.stock_location), 5.0)

    def test_without_warehouse_is_skipped(self):
        alter = self._create_alter(pick_location=False, lines=[(self.location_a, 5.0)])
        alter.subtract_physical_quantity()
        self.assertEqual(self._qty(alter, self.location_a), 5.0)

    def test_creates_pick_line_when_missing(self):
        self.env["stock.quant"]._update_available_quantity(self.product, self.location_a, 4.0)
        alter = self._create_alter()
        alter.subtract_physical_quantity()
        self.assertEqual(self._qty(alter, self.stock_location), 4.0)

    def test_pick_line_adjusted_to_real_quantity(self):
        self.env["stock.quant"]._update_available_quantity(self.product, self.location_a, 3.0)
        alter = self._create_alter(lines=[(self.stock_location, 5.0)])
        alter.subtract_physical_quantity()
        self.assertEqual(self._qty(alter, self.stock_location), 3.0)

    def test_pick_line_adjusted_to_zero_is_removed(self):
        alter = self._create_alter(lines=[(self.stock_location, 5.0)])
        alter.subtract_physical_quantity()
        self.assertFalse(alter.get_line(self.stock_location))

    def test_output_quant_creates_and_updates_output_line(self):
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.output_location, 3.0
        )
        alter = self._create_alter()
        alter.subtract_physical_quantity()
        self.assertEqual(self._qty(alter, self.output_location), 3.0)

        alter.get_line(self.output_location).available_qty = 1.0
        alter.subtract_physical_quantity()
        self.assertEqual(self._qty(alter, self.output_location), 3.0)

    def test_output_line_without_quant_is_removed(self):
        alter = self._create_alter(lines=[(self.output_location, 3.0)])
        alter.subtract_physical_quantity()
        self.assertFalse(alter.get_line(self.output_location))

    def test_output_line_with_empty_quant_is_removed(self):
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.output_location, 3.0
        )
        self.env["stock.quant"]._update_available_quantity(
            self.product, self.output_location, -3.0
        )
        alter = self._create_alter(lines=[(self.output_location, 3.0)])
        alter.subtract_physical_quantity()
        self.assertFalse(alter.get_line(self.output_location))


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestAlterLocationLineChatter(AlterLocationCommon):
    def test_create_and_write_post_messages(self):
        alter = self._create_alter()
        messages_before = len(alter.message_ids)
        line = self.env["stock.picking.alter.location.line"].create(
            {
                "stock_alter_location_id": alter.id,
                "location_id": self.location_a.id,
                "available_qty": 2.0,
            }
        )
        self.assertEqual(len(alter.message_ids), messages_before + 1)
        line.write({"available_qty": 5.0})
        self.assertEqual(len(alter.message_ids), messages_before + 2)
        line.write({"location_id": self.location_b.id})
        self.assertEqual(len(alter.message_ids), messages_before + 2)


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestMoveAlterLocationQuantitiesWizard(AlterLocationCommon):
    def _wizard(self, alter, **vals):
        values = {"stock_alter_location_id": alter.id if alter else False}
        values.update(vals)
        return self.env["move.alter.location.qtities.wizard"].create(values)

    def test_allowed_locations_with_alter(self):
        alter = self._create_alter(
            lines=[
                (self.location_a, 4.0),
                (self.output_location, 3.0),
                (self.stock_location, 1.0),
            ]
        )
        wizard = self._wizard(alter, from_location=self.location_a.id)
        self.assertEqual(
            wizard.allowed_from_location_ids, self.location_a | self.stock_location
        )
        self.assertNotIn(self.location_a, wizard.allowed_to_location_ids)
        self.assertNotIn(self.output_location, wizard.allowed_to_location_ids)
        self.assertIn(self.location_b, wizard.allowed_to_location_ids)
        self.assertIn(self.stock_location, wizard.allowed_to_location_ids)

    def test_allowed_locations_without_alter(self):
        wizard = self._wizard(False)
        self.assertFalse(wizard.allowed_from_location_ids)
        self.assertIn(self.location_a, wizard.allowed_to_location_ids)

    def test_onchange_same_location_is_cleared(self):
        alter = self._create_alter(lines=[(self.location_a, 4.0)])
        wizard = self._wizard(alter)
        wizard.from_location = self.location_a
        wizard.to_location = self.location_a
        wizard._onchange_exclude_same_location()
        self.assertFalse(wizard.to_location)

        wizard.to_location = self.location_a
        wizard.from_location = False
        wizard._onchange_exclude_same_location()
        self.assertEqual(wizard.to_location, self.location_a)

    def test_transfer_without_source_line_raises(self):
        alter = self._create_alter()
        wizard = self._wizard(
            alter,
            from_location=self.location_a.id,
            to_location=self.location_b.id,
            transfer_quantity=1.0,
        )
        with self.assertRaises(UserError):
            wizard.action_transfer_quantities()

    def test_transfer_more_than_available_raises(self):
        alter = self._create_alter(lines=[(self.location_a, 1.0)])
        wizard = self._wizard(
            alter,
            from_location=self.location_a.id,
            to_location=self.location_b.id,
            transfer_quantity=5.0,
        )
        with self.assertRaises(UserError):
            wizard.action_transfer_quantities()

    def test_transfer_over_maximum_raises(self):
        alter = self._create_alter(
            lines=[(self.location_a, 5.0)],
            max_quantity=2.0,
        )
        wizard = self._wizard(
            alter,
            from_location=self.location_a.id,
            to_location=self.stock_location.id,
            transfer_quantity=3.0,
        )
        with self.assertRaises(UserError):
            wizard.action_transfer_quantities()

    def test_transfer_under_minimum_raises(self):
        alter = self._create_alter(
            lines=[(self.stock_location, 5.0)],
            min_quantity=4.0,
        )
        wizard = self._wizard(
            alter,
            from_location=self.stock_location.id,
            to_location=self.location_a.id,
            transfer_quantity=3.0,
        )
        with self.assertRaises(UserError):
            wizard.action_transfer_quantities()

    def test_transfer_to_pick_location(self):
        alter = self._create_alter(
            lines=[(self.location_a, 5.0), (self.stock_location, 1.0)],
            max_quantity=10.0,
        )
        wizard = self._wizard(
            alter,
            from_location=self.location_a.id,
            to_location=self.stock_location.id,
            transfer_quantity=3.0,
        )
        wizard.action_transfer_quantities()
        self.assertEqual(self._qty(alter, self.location_a), 2.0)
        self.assertEqual(self._qty(alter, self.stock_location), 4.0)

    def test_transfer_from_pick_location(self):
        alter = self._create_alter(
            lines=[(self.stock_location, 5.0)],
            min_quantity=1.0,
        )
        wizard = self._wizard(
            alter,
            from_location=self.stock_location.id,
            to_location=self.location_a.id,
            transfer_quantity=3.0,
        )
        wizard.action_transfer_quantities()
        self.assertEqual(self._qty(alter, self.stock_location), 2.0)
        self.assertEqual(self._qty(alter, self.location_a), 3.0)
