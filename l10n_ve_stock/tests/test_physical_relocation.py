from unittest.mock import patch

from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestPhysicalRelocation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.use_alternate_locations = True
        cls.env.company.physical_relocation_transfer = True
        cls.env.user.group_ids = [(4, cls.env.ref("stock.group_stock_manager").id)]
        cls.warehouse = cls.env["stock.warehouse"].create(
            {"name": "Relocation Warehouse", "code": "RLW"}
        )
        cls.other_warehouse = cls.env["stock.warehouse"].create(
            {"name": "Relocation Other Warehouse", "code": "RLO"}
        )
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.location_a = cls._create_location("Shelf A", cls.stock_location)
        cls.location_b = cls._create_location("Shelf B", cls.stock_location)
        cls.location_c = cls._create_location("Shelf C", cls.stock_location)
        cls.other_location = cls._create_location(
            "Other Shelf", cls.other_warehouse.lot_stock_id
        )
        cls.template = cls.env["product.template"].create(
            {
                "name": "Relocation Product",
                "type": "consu",
                "is_storable": True,
                "physical_location_id": cls.location_a.id,
                "physical_locations_ids": [(6, 0, cls.location_a.ids)],
            }
        )
        cls.variant = cls.template.product_variant_id

    @classmethod
    def _create_location(cls, name, parent):
        return cls.env["stock.location"].create(
            {"name": name, "location_id": parent.id, "usage": "internal"}
        )

    def _add_stock(self, location, quantity, reserved=0.0):
        self.env["stock.quant"]._update_available_quantity(self.variant, location, quantity)
        quant = self.env["stock.quant"].search(
            [("product_id", "=", self.variant.id), ("location_id", "=", location.id)]
        )
        if reserved:
            quant.sudo().write({"reserved_quantity": reserved})
        return quant

    def _alter(self, warehouse=None):
        return self.env["stock.picking.alter.location"].search(
            [
                ("product_id", "=", self.variant.id),
                ("warehouse_id", "=", (warehouse or self.warehouse).id),
            ]
        )

    def _editing(self, locations):
        """Template being edited in the form: persisted values as _origin."""
        return self.template.new(
            {"physical_locations_ids": [(6, 0, locations.ids)]}, origin=self.template
        )

    def _relocation_pickings(self):
        return self.env["stock.picking"].search(
            [("is_physical_relocation", "=", True), ("product_id", "=", self.variant.id)]
        )

    # Reserved stock warning

    def test_warning_when_replaced_location_has_reserved_stock(self):
        self._add_stock(self.location_a, 10.0, reserved=4.0)
        editing = self._editing(self.location_b)
        self.assertTrue(editing.show_physical_relocation_reserved_warning)

    def test_warning_shown_in_product_form(self):
        self._add_stock(self.location_a, 10.0, reserved=4.0)
        with Form(self.template) as product_form:
            self.assertFalse(product_form.show_physical_relocation_reserved_warning)
            # Only adding a location is not a substitution.
            product_form.physical_locations_ids.add(self.location_b)
            self.assertFalse(product_form.show_physical_relocation_reserved_warning)
            product_form.physical_locations_ids.remove(id=self.location_a.id)
            self.assertTrue(product_form.show_physical_relocation_reserved_warning)
            # Only removing a location is not a substitution either.
            product_form.physical_locations_ids.remove(id=self.location_b.id)
            self.assertFalse(product_form.show_physical_relocation_reserved_warning)
            product_form.physical_locations_ids.add(self.location_a)

    def test_no_warning_without_reserved_stock(self):
        self._add_stock(self.location_a, 10.0)
        editing = self._editing(self.location_b)
        self.assertFalse(editing.show_physical_relocation_reserved_warning)

    def test_no_warning_when_nothing_is_removed(self):
        self._add_stock(self.location_a, 10.0, reserved=4.0)
        editing = self._editing(self.location_a | self.location_b)
        self.assertFalse(editing.show_physical_relocation_reserved_warning)

    def test_no_warning_when_nothing_is_added(self):
        self._add_stock(self.location_a, 10.0, reserved=4.0)
        editing = self._editing(self.env["stock.location"])
        self.assertFalse(editing.show_physical_relocation_reserved_warning)

    def test_no_warning_when_relocation_transfer_is_disabled(self):
        self.env.company.physical_relocation_transfer = False
        self._add_stock(self.location_a, 10.0, reserved=4.0)
        editing = self._editing(self.location_b)
        self.assertFalse(editing.show_physical_relocation_reserved_warning)

    def test_no_warning_when_alternate_locations_are_disabled(self):
        self.env.company.use_alternate_locations = False
        self._add_stock(self.location_a, 10.0, reserved=4.0)
        editing = self._editing(self.location_b)
        self.assertFalse(editing.show_physical_relocation_reserved_warning)

    def test_no_warning_without_stock_manager(self):
        self._add_stock(self.location_a, 10.0, reserved=4.0)
        user = self.env["res.users"].create(
            {
                "name": "Stock User Warning",
                "login": "stock_user_warning",
                "group_ids": [(6, 0, [self.env.ref("stock.group_stock_user").id])],
            }
        )
        editing = self._editing(self.location_b).with_user(user)
        self.assertFalse(editing.show_physical_relocation_reserved_warning)

    # Automatic relocation

    def test_replacing_location_moves_free_stock(self):
        self._add_stock(self.location_a, 10.0, reserved=4.0)
        alter = self._alter()
        alter.stock_alter_location_lines = [
            (0, 0, {"location_id": self.location_a.id, "available_qty": 10.0})
        ]

        self.template.write({"physical_locations_ids": [(6, 0, self.location_b.ids)]})

        picking = self._relocation_pickings()
        self.assertEqual(len(picking), 1)
        self.assertEqual(picking.state, "done")
        self.assertEqual(picking.location_dest_id, self.location_b)
        self.assertEqual(self.variant.with_context(location=self.location_b.id).qty_available, 6.0)
        self.assertEqual(self.variant.with_context(location=self.location_a.id).qty_available, 4.0)
        self.assertEqual(alter.get_line(self.location_a).available_qty, 4.0)
        self.assertEqual(alter.get_line(self.location_b).available_qty, 6.0)

    def test_replacing_location_with_only_reserved_stock_creates_no_transfer(self):
        self._add_stock(self.location_a, 5.0, reserved=5.0)
        self.template.write({"physical_locations_ids": [(6, 0, self.location_b.ids)]})
        self.assertFalse(self._relocation_pickings())
        self.assertTrue(self._alter().get_line(self.location_b))

    def test_relocation_disabled_by_company_flags(self):
        self._add_stock(self.location_a, 5.0)
        self.env.company.physical_relocation_transfer = False
        result = self.template._relocate_physical_stock(self.location_a, self.location_b)
        self.assertFalse(result)
        self.env.company.physical_relocation_transfer = True
        self.env.company.use_alternate_locations = False
        result = self.template._relocate_physical_stock(self.location_a, self.location_b)
        self.assertFalse(result)

    def test_relocation_requires_stock_manager(self):
        self._add_stock(self.location_a, 5.0)
        user = self.env["res.users"].create(
            {
                "name": "Stock User Relocation",
                "login": "stock_user_relocation",
                "group_ids": [(6, 0, [self.env.ref("stock.group_stock_user").id])],
            }
        )
        result = self.template.with_user(user)._relocate_physical_stock(
            self.location_a, self.location_b
        )
        self.assertFalse(result)

    def test_pair_relocations(self):
        tmpl = self.template
        a, b, c = self.location_a, self.location_b, self.location_c
        self.assertEqual(tmpl._pair_relocations(a, a | b), [])
        self.assertEqual(tmpl._pair_relocations(a | b, a), [])
        self.assertEqual(tmpl._pair_relocations(a, b), [(a, b)])
        self.assertEqual(tmpl._pair_relocations(a | b, c), [(a, c), (b, c)])

    def test_transfer_between_same_or_empty_locations(self):
        self._add_stock(self.location_a, 5.0)
        tmpl = self.template.sudo()
        self.assertFalse(tmpl._transfer_between_locations(self.location_a, self.location_a))
        self.assertFalse(
            tmpl._transfer_between_locations(self.location_a, self.env["stock.location"])
        )

    def test_transfer_without_operation_type(self):
        self._add_stock(self.location_a, 5.0)
        tmpl = self.template.sudo()
        with patch.object(
            type(tmpl),
            "_internal_operation_type",
            return_value=self.env["stock.picking.type"],
        ):
            self.assertFalse(tmpl._transfer_between_locations(self.location_a, self.location_b))

    def test_internal_operation_type(self):
        tmpl = self.template
        self.assertEqual(
            tmpl._internal_operation_type(self.location_a, self.location_b),
            self.warehouse.int_type_id,
        )
        orphan = self.env["stock.location"].create({"name": "Orphan", "usage": "internal"})
        picking_type = tmpl._internal_operation_type(orphan, orphan)
        self.assertEqual(picking_type.code, "internal")

    def _validate_returning(self, action):
        picking_class = type(self.env["stock.picking"])
        original = picking_class.button_validate

        def fake_button_validate(pickings):
            original(pickings)
            return dict(action, context={"button_validate_picking_ids": pickings.ids})

        return patch.object(picking_class, "button_validate", fake_button_validate)

    def test_transfer_processes_returned_wizard(self):
        self._add_stock(self.location_a, 5.0)
        with self._validate_returning({"res_model": "stock.backorder.confirmation"}):
            picking = self.template.sudo()._transfer_between_locations(
                self.location_a, self.location_b
            )
        self.assertEqual(picking.state, "done")

    def test_transfer_ignores_returned_model_without_process(self):
        self._add_stock(self.location_a, 5.0)
        with self._validate_returning({"res_model": "stock.quantity.history"}):
            picking = self.template.sudo()._transfer_between_locations(
                self.location_a, self.location_b
            )
        self.assertEqual(picking.state, "done")

    def test_transfer_between_warehouses_keeps_ledger(self):
        self._add_stock(self.location_a, 5.0)
        alter = self._alter()
        picking = self.template.sudo()._transfer_between_locations(
            self.location_a, self.other_location
        )
        self.assertEqual(picking.state, "done")
        self.assertFalse(alter.get_line(self.other_location))

    def test_sync_ledger_without_alter_record(self):
        self._alter().unlink()
        self.template._sync_relocation_ledger(
            self.location_a, self.location_b, {self.variant: 3.0}
        )
        self.assertFalse(self._alter())

    def test_register_location_in_alter_location(self):
        alter = self._alter()
        self.template._register_location_in_alter_location(self.location_b)
        self.assertEqual(alter.get_line(self.location_b).available_qty, 0.0)
        self.template._register_location_in_alter_location(self.location_b)
        self.assertEqual(len(alter.get_line(self.location_b)), 1)

    def test_register_location_without_alter_record(self):
        orphan = self.env["stock.location"].create({"name": "Orphan", "usage": "internal"})
        self.env["stock.picking.alter.location"].search(
            [("product_id", "=", self.variant.id)]
        ).unlink()
        self.template._register_location_in_alter_location(orphan)
        self.assertFalse(
            self.env["stock.picking.alter.location.line"].search(
                [("location_id", "=", orphan.id)]
            )
        )
