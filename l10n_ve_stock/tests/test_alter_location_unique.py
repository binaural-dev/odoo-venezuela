"""One line per location in "Other Product Locations".

Regression for "Expected singleton: stock.picking.alter.location.line(...)"
raised by action_move_to_output when a physical location record had the same
location twice. Covers the SQL constraint, the initial lines built from
quants, every flow that adds or subtracts quantities by location, the
end-to-end picking validation and the pre-migrate that merges the duplicates
already stored.
"""

import importlib.util

from psycopg2 import IntegrityError

from odoo.tests import Form, TransactionCase, tagged
from odoo.tools import file_path, mute_logger

CONSTRAINT_NAME = "stock_picking_alter_location_line_location_uniq"
MIGRATION_LOGGER = "l10n_ve_stock_pre_migrate_19_0_1_0_13"
CONSTRAINT_MESSAGE_ES = "Esta ubicación ya está en las otras ubicaciones del producto."


def _load_migration(script, module_name):
    path = file_path(f"l10n_ve_stock/migrations/19.0.1.0.13/{script}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_pre_migrate():
    return _load_migration("pre-migrate.py", MIGRATION_LOGGER)


def _load_post_migrate():
    return _load_migration("post-migrate.py", "l10n_ve_stock_post_migrate_19_0_1_0_13")


class AlterLocationUniqueCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.use_alternate_locations = True
        cls.env.company.physical_relocation_transfer = False
        cls.warehouse = cls.env["stock.warehouse"].create(
            {"name": "Alter Unique Warehouse", "code": "AUW", "delivery_steps": "pick_ship"}
        )
        cls.other_warehouse = cls.env["stock.warehouse"].create(
            {"name": "Alter Unique Other Warehouse", "code": "AUO"}
        )
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.output_location = cls.warehouse.wh_output_stock_loc_id
        cls.shelf = cls._create_location("Unique Shelf", cls.stock_location)
        cls.shelf_b = cls._create_location("Unique Shelf B", cls.stock_location)
        cls.orphan_location = cls.env["stock.location"].create(
            {"name": "Unique Orphan", "usage": "internal"}
        )
        cls.product = cls._create_product("Alter Unique Product")
        cls.other_product = cls._create_product("Alter Unique Other Product")
        cls.Alter = cls.env["stock.picking.alter.location"]
        cls.Line = cls.env["stock.picking.alter.location.line"]
        cls.Quant = cls.env["stock.quant"]

    @classmethod
    def _create_location(cls, name, parent):
        return cls.env["stock.location"].create(
            {"name": name, "location_id": parent.id, "usage": "internal"}
        )

    @classmethod
    def _create_product(cls, name):
        return cls.env["product.product"].create(
            {"name": name, "type": "consu", "is_storable": True}
        )

    def _create_alter(self, product, lines, **vals):
        values = {
            "product_id": product.id,
            "pick_location": self.stock_location.id,
            "stock_alter_location_lines": [
                (0, 0, {"location_id": location.id, "available_qty": qty})
                for location, qty in lines
            ],
        }
        values.update(vals)
        return self.Alter.create(values)

    def _create_template(self, name="Alter Unique Template"):
        return self.env["product.template"].create(
            {"name": name, "type": "consu", "is_storable": True}
        )

    @classmethod
    def _activate_es_ve(cls):
        cls.env["res.lang"]._activate_lang("es_VE")
        cls.env["ir.module.module"]._load_module_terms(["l10n_ve_stock"], ["es_VE"], overwrite=True)

    def _qty_by_location(self, alter):
        return {line.location_id: line.available_qty for line in alter.stock_alter_location_lines}

    def assertOneLinePerLocation(self, alter):
        self.env.flush_all()
        self.cr.execute(
            """
            SELECT location_id, COUNT(*)
              FROM stock_picking_alter_location_line
             WHERE stock_alter_location_id = %s
          GROUP BY location_id
            HAVING COUNT(*) > 1
            """,
            (alter.id,),
        )
        self.assertFalse(self.cr.fetchall(), "A location is repeated in the record")


@tagged("post_install", "-at_install", "l10n_ve_stock", "l10n_ve_stock_alter_location_unique")
class TestAlterLocationLineConstraint(AlterLocationUniqueCommon):
    """UNIQUE(stock_alter_location_id, location_id) on every entry point."""

    def test_constraint_exists_in_database(self):
        self.cr.execute(
            """
            SELECT pg_get_constraintdef(oid)
              FROM pg_constraint
             WHERE conname = %s
            """,
            (CONSTRAINT_NAME,),
        )
        definition = self.cr.fetchone()
        self.assertTrue(definition, "The unique constraint was not created")
        self.assertEqual(definition[0], "UNIQUE (stock_alter_location_id, location_id)")

    def test_constraint_registered_with_translatable_message(self):
        # The es_VE.po entry points to this xmlid; if the name changes the
        # translation silently stops applying.
        constraint = self.env.ref(f"l10n_ve_stock.constraint_{CONSTRAINT_NAME}")
        self.assertEqual(constraint.name, CONSTRAINT_NAME)
        self.assertEqual(
            constraint.message,
            "This location is already in the other locations of the product.",
        )

    def test_repeated_location_by_create_is_rejected(self):
        alter = self._create_alter(self.product, [(self.shelf, 4.0)])
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.Line.create(
                {"stock_alter_location_id": alter.id, "location_id": self.shelf.id, "available_qty": 6.0}
            )
            self.env.flush_all()

    def test_repeated_location_in_same_create_is_rejected(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self._create_alter(self.product, [(self.shelf, 4.0), (self.shelf, 6.0)])
            self.env.flush_all()

    def test_repeated_location_from_form_is_rejected(self):
        alter = self._create_alter(self.product, [(self.shelf, 4.0)])
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            with Form(alter) as alter_form:
                with alter_form.stock_alter_location_lines.new() as line:
                    line.location_id = self.shelf
                    line.available_qty = 6.0
            self.env.flush_all()

    def test_changing_line_to_used_location_is_rejected(self):
        alter = self._create_alter(self.product, [(self.shelf, 4.0), (self.shelf_b, 6.0)])
        line_b = alter.get_line(self.shelf_b)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            line_b.location_id = self.shelf
            self.env.flush_all()

    def test_repeated_location_by_import_is_rejected(self):
        alter = self._create_alter(self.product, [(self.shelf, 4.0)])
        with mute_logger("odoo.sql_db"):
            result = self.Line.load(
                ["stock_alter_location_id/.id", "location_id/.id", "available_qty"],
                [[str(alter.id), str(self.shelf.id), "6"]],
            )
        self.assertFalse(result["ids"])
        self.assertTrue(any(m["type"] == "error" for m in result["messages"]))
        self.assertEqual(self._qty_by_location(alter), {self.shelf: 4.0})

    def test_import_error_shows_translated_message(self):
        # What a Spanish-speaking user sees, and the proof that the es_VE.po
        # entry reaches the constraint.
        self._activate_es_ve()
        alter = self._create_alter(self.product, [(self.shelf, 4.0)])
        with mute_logger("odoo.sql_db"):
            result = self.Line.with_context(lang="es_VE").load(
                ["stock_alter_location_id/.id", "location_id/.id", "available_qty"],
                [[str(alter.id), str(self.shelf.id), "6"]],
            )
        self.assertFalse(result["ids"])
        self.assertIn(CONSTRAINT_MESSAGE_ES, " ".join(m["message"] for m in result["messages"]))

    def test_same_location_in_other_record_is_allowed(self):
        alter = self._create_alter(self.product, [(self.shelf, 4.0)])
        other_alter = self._create_alter(self.other_product, [(self.shelf, 6.0)])
        self.env.flush_all()
        self.assertEqual(self._qty_by_location(alter), {self.shelf: 4.0})
        self.assertEqual(self._qty_by_location(other_alter), {self.shelf: 6.0})

    def test_distinct_locations_in_same_record_are_allowed(self):
        alter = self._create_alter(
            self.product, [(self.stock_location, 1.0), (self.shelf, 2.0), (self.shelf_b, 3.0)]
        )
        self.assertOneLinePerLocation(alter)
        self.assertEqual(len(alter.stock_alter_location_lines), 3)

    def test_location_freed_by_unlink_can_be_used_again(self):
        alter = self._create_alter(self.product, [(self.shelf, 4.0)])
        alter.get_line(self.shelf).unlink()
        self.Line.create(
            {"stock_alter_location_id": alter.id, "location_id": self.shelf.id, "available_qty": 6.0}
        )
        self.env.flush_all()
        self.assertEqual(self._qty_by_location(alter), {self.shelf: 6.0})


@tagged("post_install", "-at_install", "l10n_ve_stock", "l10n_ve_stock_alter_location_unique")
class TestAlterLinesFromQuants(AlterLocationUniqueCommon):
    """product.template._get_quants_for_alter_lines: one line per location."""

    def _lines(self, template, pick_location, warehouse=None):
        return {
            vals["location_id"]: vals["available_qty"]
            for _command, _id, vals in template._get_quants_for_alter_lines(
                pick_location, warehouse=warehouse
            )
        }

    def test_quants_of_same_location_are_summed(self):
        template = self._create_template()
        variant = template.product_variant_id
        package_1 = self.env["stock.package"].create({"name": "AUW-PACK-1"})
        package_2 = self.env["stock.package"].create({"name": "AUW-PACK-2"})
        self.Quant._update_available_quantity(variant, self.shelf, 4.0, package_id=package_1)
        self.Quant._update_available_quantity(variant, self.shelf, 6.0, package_id=package_2)
        self.Quant._update_available_quantity(variant, self.stock_location, 2.0)

        commands = template._get_quants_for_alter_lines(self.stock_location, warehouse=self.warehouse)

        self.assertEqual(len(commands), 2)
        self.assertTrue(all(command[0] == 0 for command in commands))
        self.assertEqual(
            self._lines(template, self.stock_location, self.warehouse),
            {self.shelf.id: 10.0, self.stock_location.id: 2.0},
        )

    def test_summed_quantity_is_rounded_to_the_unit_of_measure(self):
        # 0.1 + 0.2 is 0.30000000000000004 in floating point.
        template = self._create_template()
        variant = template.product_variant_id
        for qty, name in ((0.1, "AUW-ROUND-1"), (0.2, "AUW-ROUND-2")):
            package = self.env["stock.package"].create({"name": name})
            self.Quant._update_available_quantity(variant, self.shelf, qty, package_id=package)

        self.assertEqual(
            self._lines(template, self.stock_location, self.warehouse), {self.shelf.id: 0.3}
        )

    def test_quants_of_same_location_by_lot_are_summed(self):
        template = self._create_template()
        template.tracking = "lot"
        variant = template.product_variant_id
        lot_1 = self.env["stock.lot"].create({"name": "AUW-LOT-1", "product_id": variant.id})
        lot_2 = self.env["stock.lot"].create({"name": "AUW-LOT-2", "product_id": variant.id})
        self.Quant._update_available_quantity(variant, self.shelf, 3.0, lot_id=lot_1)
        self.Quant._update_available_quantity(variant, self.shelf, 5.0, lot_id=lot_2)

        self.assertEqual(self._lines(template, self.stock_location, self.warehouse), {self.shelf.id: 8.0})

    def test_non_positive_quants_are_ignored(self):
        template = self._create_template()
        variant = template.product_variant_id
        package = self.env["stock.package"].create({"name": "AUW-PACK-NEG"})
        self.Quant._update_available_quantity(variant, self.shelf, 5.0, package_id=package)
        self.Quant._update_available_quantity(variant, self.shelf, -3.0)
        self.Quant._update_available_quantity(variant, self.shelf_b, -2.0)

        # Only the positive quant counts in Shelf; Shelf B has no line at all.
        self.assertEqual(self._lines(template, self.stock_location, self.warehouse), {self.shelf.id: 5.0})

    def test_reserved_quantity_is_not_available(self):
        template = self._create_template()
        variant = template.product_variant_id
        self.Quant._update_available_quantity(variant, self.shelf, 5.0, reserved_quantity=2.0)

        self.assertEqual(self._lines(template, self.stock_location, self.warehouse), {self.shelf.id: 3.0})

    def test_quants_of_other_warehouse_are_excluded(self):
        template = self._create_template()
        variant = template.product_variant_id
        self.Quant._update_available_quantity(variant, self.shelf, 4.0)
        self.Quant._update_available_quantity(variant, self.other_warehouse.lot_stock_id, 9.0)

        self.assertEqual(self._lines(template, self.stock_location, self.warehouse), {self.shelf.id: 4.0})

    def test_warehouse_is_resolved_from_pick_location(self):
        template = self._create_template()
        variant = template.product_variant_id
        self.Quant._update_available_quantity(variant, self.shelf, 4.0)

        self.assertEqual(self._lines(template, self.shelf), {self.shelf.id: 4.0})

    def test_pick_location_without_warehouse_returns_nothing(self):
        template = self._create_template()
        self.Quant._update_available_quantity(template.product_variant_id, self.shelf, 4.0)

        self.assertEqual(template._get_quants_for_alter_lines(self.orphan_location), [])

    def test_product_without_quants_returns_nothing(self):
        template = self._create_template()

        self.assertEqual(
            template._get_quants_for_alter_lines(self.stock_location, warehouse=self.warehouse), []
        )

    def test_sync_from_physical_locations_creates_one_line_per_location(self):
        template = self._create_template()
        variant = template.product_variant_id
        package_1 = self.env["stock.package"].create({"name": "AUW-SYNC-1"})
        package_2 = self.env["stock.package"].create({"name": "AUW-SYNC-2"})
        self.Quant._update_available_quantity(variant, self.stock_location, 4.0, package_id=package_1)
        self.Quant._update_available_quantity(variant, self.stock_location, 6.0, package_id=package_2)

        template.write({"physical_locations_ids": [(6, 0, self.stock_location.ids)]})

        alter = self.Alter.search([("product_id", "=", variant.id)])
        self.assertOneLinePerLocation(alter)
        self.assertEqual(self._qty_by_location(alter), {self.stock_location: 10.0})
        self.assertEqual(alter.pick_quantity, 10.0)

    def test_create_or_update_creates_one_line_per_location(self):
        template = self._create_template()
        variant = template.product_variant_id
        package_1 = self.env["stock.package"].create({"name": "AUW-CREATE-1"})
        package_2 = self.env["stock.package"].create({"name": "AUW-CREATE-2"})
        self.Quant._update_available_quantity(variant, self.shelf, 4.0, package_id=package_1)
        self.Quant._update_available_quantity(variant, self.shelf, 6.0, package_id=package_2)
        template.physical_location_id = self.shelf
        self.Alter.search([("product_id", "=", variant.id)]).unlink()

        template._create_or_update_alter_location()

        alter = self.Alter.search([("product_id", "=", variant.id)])
        self.assertOneLinePerLocation(alter)
        self.assertEqual(self._qty_by_location(alter), {self.shelf: 10.0})


@tagged("post_install", "-at_install", "l10n_ve_stock", "l10n_ve_stock_alter_location_unique")
class TestAlterFlowsKeepOneLine(AlterLocationUniqueCommon):
    """Every flow that adds or subtracts by location updates the existing line."""

    def test_receive_quantity_updates_existing_line(self):
        alter = self._create_alter(self.product, [(self.shelf, 4.0)])
        alter.action_receive_quantity(self.shelf.id, 6.0)
        self.assertOneLinePerLocation(alter)
        self.assertEqual(self._qty_by_location(alter), {self.shelf: 10.0})

    def test_repeated_moves_to_output_update_existing_lines(self):
        alter = self._create_alter(self.product, [(self.stock_location, 10.0)])
        alter.action_move_to_output(self.output_location.id, 3.0, self.stock_location.id)
        alter.action_move_to_output(self.output_location.id, 2.0, self.stock_location.id)
        self.assertOneLinePerLocation(alter)
        self.assertEqual(
            self._qty_by_location(alter), {self.stock_location: 5.0, self.output_location: 5.0}
        )

    def test_deliver_from_output_updates_existing_line(self):
        alter = self._create_alter(self.product, [(self.output_location, 5.0)])
        alter.action_deliver_from_output(self.output_location.id, 2.0)
        self.assertOneLinePerLocation(alter)
        self.assertEqual(self._qty_by_location(alter), {self.output_location: 3.0})

    def test_internal_transfer_to_existing_line(self):
        alter = self._create_alter(self.product, [(self.shelf, 4.0), (self.shelf_b, 1.0)])
        alter.action_internal_transfer(self.shelf.id, self.shelf_b.id, 3.0)
        self.assertOneLinePerLocation(alter)
        self.assertEqual(self._qty_by_location(alter), {self.shelf: 1.0, self.shelf_b: 4.0})

    def test_wizard_transfer_to_existing_line(self):
        alter = self._create_alter(self.product, [(self.shelf, 4.0), (self.stock_location, 1.0)])
        wizard = self.env["move.alter.location.qtities.wizard"].create(
            {
                "stock_alter_location_id": alter.id,
                "from_location": self.shelf.id,
                "to_location": self.stock_location.id,
                "transfer_quantity": 3.0,
            }
        )
        wizard.action_transfer_quantities()
        self.assertOneLinePerLocation(alter)
        self.assertEqual(self._qty_by_location(alter), {self.shelf: 1.0, self.stock_location: 4.0})

    def test_subtract_physical_quantity_adjusts_existing_pick_line(self):
        self.Quant._update_available_quantity(self.product, self.stock_location, 7.0)
        alter = self._create_alter(self.product, [(self.stock_location, 10.0)])
        alter.subtract_physical_quantity()
        self.assertOneLinePerLocation(alter)
        self.assertEqual(self._qty_by_location(alter), {self.stock_location: 7.0})

    def test_register_existing_location_does_not_add_line(self):
        template = self._create_template()
        variant = template.product_variant_id
        alter = self._create_alter(variant, [(self.shelf, 4.0)])
        template._register_location_in_alter_location(self.shelf)
        self.assertOneLinePerLocation(alter)
        self.assertEqual(self._qty_by_location(alter), {self.shelf: 4.0})

    def test_relocation_ledger_updates_existing_lines(self):
        template = self._create_template()
        variant = template.product_variant_id
        alter = self._create_alter(variant, [(self.shelf, 4.0), (self.shelf_b, 1.0)])
        template._sync_relocation_ledger(self.shelf, self.shelf_b, {variant: 3.0})
        self.assertOneLinePerLocation(alter)
        self.assertEqual(self._qty_by_location(alter), {self.shelf: 1.0, self.shelf_b: 4.0})


@tagged("post_install", "-at_install", "l10n_ve_stock", "l10n_ve_stock_alter_location_unique")
class TestPickingWithPackagesRegression(AlterLocationUniqueCommon):
    """End-to-end: the scenario of the original traceback.

    A product stored in two packages in its physical location used to get two
    lines for that location; validating the pick to Output then raised
    "Expected singleton" inside action_move_to_output.
    """

    def _done_picking(self, picking_type, source, destination, product, qty):
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

    def test_pick_and_delivery_with_packages_in_physical_location(self):
        template = self._create_template("Alter Unique Packages Picking")
        variant = template.product_variant_id
        package_1 = self.env["stock.package"].create({"name": "AUW-PICK-1"})
        package_2 = self.env["stock.package"].create({"name": "AUW-PICK-2"})
        self.Quant._update_available_quantity(variant, self.stock_location, 4.0, package_id=package_1)
        self.Quant._update_available_quantity(variant, self.stock_location, 6.0, package_id=package_2)
        template.write({"physical_locations_ids": [(6, 0, self.stock_location.ids)]})
        alter = self.Alter.search([("product_id", "=", variant.id)])
        self.assertEqual(self._qty_by_location(alter), {self.stock_location: 10.0})

        pick = self._done_picking(
            self.warehouse.pick_type_id, self.stock_location, self.output_location, variant, 5.0
        )

        self.assertEqual(pick.state, "done")
        self.assertOneLinePerLocation(alter)
        self.assertEqual(
            self._qty_by_location(alter), {self.stock_location: 5.0, self.output_location: 5.0}
        )

        delivery = self._done_picking(
            self.warehouse.out_type_id,
            self.output_location,
            self.env.ref("stock.stock_location_customers"),
            variant,
            5.0,
        )

        self.assertEqual(delivery.state, "done")
        self.assertOneLinePerLocation(alter)
        self.assertEqual(self._qty_by_location(alter), {self.stock_location: 5.0})


class MergeMigrationCommon(AlterLocationUniqueCommon):
    """Database as pre-migrate finds it: duplicated lines, no constraint."""

    def setUp(self):
        super().setUp()
        self.migration = _load_pre_migrate()

    def _drop_constraint(self):
        self.env.flush_all()
        self.cr.execute(
            f"ALTER TABLE stock_picking_alter_location_line DROP CONSTRAINT {CONSTRAINT_NAME}"
        )

    def _insert_lines(self, alter_id, location_id, quantities):
        ids = []
        for qty in quantities:
            self.cr.execute(
                """
                INSERT INTO stock_picking_alter_location_line
                       (stock_alter_location_id, location_id, available_qty)
                VALUES (%s, %s, %s)
             RETURNING id
                """,
                (alter_id, location_id, qty),
            )
            ids.append(self.cr.fetchone()[0])
        self.env.invalidate_all()
        return ids

    def _merge(self):
        self.migration.merge_duplicated_alter_location_lines(self.cr)
        self.env.invalidate_all()

    def _line_rows(self, alter):
        self.cr.execute(
            "SELECT id, location_id, available_qty FROM stock_picking_alter_location_line "
            "WHERE stock_alter_location_id = %s ORDER BY id",
            (alter.id,),
        )
        return self.cr.fetchall()



@tagged("post_install", "-at_install", "l10n_ve_stock", "l10n_ve_stock_alter_location_unique")
class TestMergeDuplicatedLinesMigration(MergeMigrationCommon):
    """pre-migrate 19.0.1.0.13: merge the duplicates before the constraint."""

    def test_duplicates_merged_by_summing_without_changing_totals(self):
        alter = self._create_alter(self.product, [(self.shelf, 1.0), (self.output_location, 2.0)])
        self._drop_constraint()
        self._insert_lines(alter.id, self.stock_location.id, [4.0, 6.0])
        self.assertEqual(len(alter.get_line(self.stock_location)), 2)
        totals_before = (alter.pick_quantity, alter.total_alter_quantity, alter.total_quantity)
        self.assertEqual(totals_before, (10.0, 11.0, 1.0))

        self._merge()

        self.assertOneLinePerLocation(alter)
        self.assertEqual(
            self._qty_by_location(alter),
            {self.stock_location: 10.0, self.shelf: 1.0, self.output_location: 2.0},
        )
        self.assertEqual(
            (alter.pick_quantity, alter.total_alter_quantity, alter.total_quantity),
            totals_before,
        )

    def test_lowest_id_line_is_kept(self):
        alter = self._create_alter(self.product, [])
        self._drop_constraint()
        line_ids = self._insert_lines(alter.id, self.stock_location.id, [4.0, 6.0, 1.5])

        self._merge()

        self.assertEqual(self._line_rows(alter), [(min(line_ids), self.stock_location.id, 11.5)])

    def test_several_groups_and_records_are_merged_independently(self):
        alter = self._create_alter(self.product, [])
        other_alter = self._create_alter(self.other_product, [])
        self._drop_constraint()
        self._insert_lines(alter.id, self.stock_location.id, [1.0, 2.0])
        self._insert_lines(alter.id, self.shelf.id, [3.0, 4.0, 5.0])
        self._insert_lines(other_alter.id, self.stock_location.id, [10.0, 20.0])

        self._merge()

        self.assertEqual(self._qty_by_location(alter), {self.stock_location: 3.0, self.shelf: 12.0})
        self.assertEqual(self._qty_by_location(other_alter), {self.stock_location: 30.0})

    def test_negative_and_empty_quantities_are_summed(self):
        alter = self._create_alter(self.product, [])
        self._drop_constraint()
        self._insert_lines(alter.id, self.stock_location.id, [5.0, -2.0, None])

        self._merge()

        self.assertEqual(self._qty_by_location(alter), {self.stock_location: 3.0})

    def test_lines_without_record_or_location_are_untouched(self):
        alter = self._create_alter(self.product, [])
        self._drop_constraint()
        orphan_ids = self._insert_lines(None, self.stock_location.id, [1.0, 2.0])
        no_location_ids = self._insert_lines(alter.id, None, [3.0, 4.0])

        self._merge()

        self.cr.execute(
            "SELECT id, available_qty FROM stock_picking_alter_location_line WHERE id = ANY(%s) ORDER BY id",
            (orphan_ids + no_location_ids,),
        )
        self.assertEqual(
            self.cr.fetchall(),
            list(zip(orphan_ids + no_location_ids, [1.0, 2.0, 3.0, 4.0])),
        )

    def test_without_duplicates_nothing_changes(self):
        alter = self._create_alter(self.product, [(self.stock_location, 5.0), (self.shelf, 2.0)])
        self.env.flush_all()
        before = self._line_rows(alter)

        with self.assertNoLogs(MIGRATION_LOGGER, level="INFO"):
            self._merge()

        self.assertEqual(self._line_rows(alter), before)

    def test_each_merge_is_logged_for_audit(self):
        alter = self._create_alter(self.product, [])
        self._drop_constraint()
        line_ids = self._insert_lines(alter.id, self.stock_location.id, [4.0, 6.0])

        with self.assertLogs(MIGRATION_LOGGER, level="INFO") as logs:
            self._merge()

        self.assertEqual(len(logs.output), 2)
        self.assertIn(f"record {alter.id}, location {self.stock_location.id}", logs.output[0])
        self.assertIn(str(line_ids), logs.output[0])
        self.assertIn("Merged 1 groups", logs.output[1])

    def test_constraint_can_be_created_after_merge(self):
        alter = self._create_alter(self.product, [])
        self._drop_constraint()
        self._insert_lines(alter.id, self.stock_location.id, [4.0, 6.0])

        self._merge()

        # What the ORM does right after pre-migrate; it fails if any
        # duplicate is left.
        self.cr.execute(
            f"ALTER TABLE stock_picking_alter_location_line ADD CONSTRAINT {CONSTRAINT_NAME} "
            "UNIQUE (stock_alter_location_id, location_id)"
        )

    def test_merged_record_allows_move_to_output(self):
        alter = self._create_alter(self.product, [])
        self._drop_constraint()
        self._insert_lines(alter.id, self.stock_location.id, [4.0, 6.0])
        self._merge()

        alter.action_move_to_output(self.output_location.id, 3.0, self.stock_location.id)

        self.assertEqual(
            self._qty_by_location(alter), {self.stock_location: 7.0, self.output_location: 3.0}
        )

    def test_migrate_entry_point_merges_on_upgrade(self):
        alter = self._create_alter(self.product, [])
        self._drop_constraint()
        self._insert_lines(alter.id, self.stock_location.id, [4.0, 6.0])

        self.migration.migrate(self.cr, "19.0.1.0.12")
        self.env.invalidate_all()

        self.assertEqual(self._qty_by_location(alter), {self.stock_location: 10.0})

    def test_migrate_entry_point_skips_fresh_install(self):
        alter = self._create_alter(self.product, [])
        self._drop_constraint()
        line_ids = self._insert_lines(alter.id, self.stock_location.id, [4.0, 6.0])

        self.migration.migrate(self.cr, None)
        self.env.invalidate_all()

        self.assertEqual(sorted(alter.get_line(self.stock_location).ids), sorted(line_ids))

    def test_upgrade_from_version_without_the_table_does_nothing(self):
        # Databases installed before 19.0.1.0.6 have no line table when
        # pre-migrate runs.
        self.env.flush_all()
        self.cr.execute(
            "ALTER TABLE stock_picking_alter_location_line RENAME TO tmp_alter_line_backup"
        )
        try:
            with self.assertNoLogs(MIGRATION_LOGGER, level="INFO"):
                self.migration.migrate(self.cr, "19.0.1.0.5")
        finally:
            self.cr.execute(
                "ALTER TABLE tmp_alter_line_backup RENAME TO stock_picking_alter_location_line"
            )

    def test_external_ids_of_removed_lines_are_deleted(self):
        alter = self._create_alter(self.product, [])
        self._drop_constraint()
        kept_id, removed_id = self._insert_lines(alter.id, self.stock_location.id, [4.0, 6.0])
        for line_id, name in ((kept_id, "kept_line"), (removed_id, "removed_line")):
            self.env["ir.model.data"].create(
                {
                    "module": "__import__",
                    "name": name,
                    "model": "stock.picking.alter.location.line",
                    "res_id": line_id,
                }
            )

        self._merge()

        self.assertTrue(self.env.ref("__import__.kept_line", raise_if_not_found=False))
        self.assertFalse(self.env.ref("__import__.removed_line", raise_if_not_found=False))

    def test_kept_line_write_date_is_updated(self):
        alter = self._create_alter(self.product, [])
        self._drop_constraint()
        kept_id, _removed_id = self._insert_lines(alter.id, self.stock_location.id, [4.0, 6.0])
        self.cr.execute(
            "UPDATE stock_picking_alter_location_line SET write_date = '2020-01-01' WHERE id = %s",
            (kept_id,),
        )

        self._merge()

        self.cr.execute(
            "SELECT write_date > '2020-01-01' FROM stock_picking_alter_location_line WHERE id = %s",
            (kept_id,),
        )
        self.assertTrue(self.cr.fetchone()[0])


@tagged("post_install", "-at_install", "l10n_ve_stock", "l10n_ve_stock_alter_location_unique")
class TestMergedLinesChatterMigration(MergeMigrationCommon):
    """post-migrate 19.0.1.0.13: the merge is left in each record's chatter."""

    def setUp(self):
        super().setUp()
        self.post_migration = _load_post_migrate()

    def _merge_messages(self, alter):
        return alter.message_ids.filtered(
            lambda message: "were merged into one" in (message.body or "")
            or "se fusionaron" in (message.body or "")
        )

    def _table_exists(self, name):
        self.cr.execute("SELECT to_regclass(%s) IS NOT NULL", (name,))
        return self.cr.fetchone()[0]

    def test_merge_is_posted_in_the_chatter_of_each_record(self):
        alter = self._create_alter(self.product, [])
        other_alter = self._create_alter(self.other_product, [])
        untouched = self._create_alter(self._create_product("Alter Unique Untouched"), [(self.shelf, 1.0)])
        self._drop_constraint()
        self._insert_lines(alter.id, self.stock_location.id, [4.0, 6.5])
        self._insert_lines(other_alter.id, self.shelf.id, [1.0, 2.0])
        self._merge()

        self.post_migration.migrate(self.cr, "19.0.1.0.12")

        message = self._merge_messages(alter)
        self.assertEqual(len(message), 1)
        self.assertIn(self.stock_location.display_name, message.body)
        self.assertIn("4, 6.5", message.body)
        self.assertIn("10.5", message.body)
        self.assertEqual(len(self._merge_messages(other_alter)), 1)
        self.assertFalse(self._merge_messages(untouched))
        self.assertFalse(self._table_exists(self.migration.MERGE_LOG_TABLE))

    def test_message_uses_the_admin_language(self):
        self._activate_es_ve()
        self.env.ref("base.user_admin").lang = "es_VE"
        alter = self._create_alter(self.product, [])
        self._drop_constraint()
        self._insert_lines(alter.id, self.stock_location.id, [4.0, 6.0])
        self._merge()

        self.post_migration.migrate(self.cr, "19.0.1.0.12")

        message = self._merge_messages(alter)
        self.assertEqual(len(message), 1)
        self.assertIn("se fusionaron en una sola con 10", message.body)

    def test_deleted_record_is_skipped(self):
        alter = self._create_alter(self.product, [])
        self._drop_constraint()
        self._insert_lines(alter.id, self.stock_location.id, [4.0, 6.0])
        self._merge()
        alter.unlink()

        self.post_migration.migrate(self.cr, "19.0.1.0.12")

        self.assertFalse(self._table_exists(self.migration.MERGE_LOG_TABLE))

    def test_without_merges_nothing_is_posted(self):
        alter = self._create_alter(self.product, [(self.stock_location, 5.0)])
        self._merge()
        messages_before = alter.message_ids

        self.post_migration.migrate(self.cr, "19.0.1.0.12")

        self.assertEqual(alter.message_ids, messages_before)

    def test_fresh_install_does_nothing(self):
        alter = self._create_alter(self.product, [])
        self._drop_constraint()
        self._insert_lines(alter.id, self.stock_location.id, [4.0, 6.0])
        self._merge()

        self.post_migration.migrate(self.cr, None)

        self.assertFalse(self._merge_messages(alter))
        self.assertTrue(self._table_exists(self.migration.MERGE_LOG_TABLE))
