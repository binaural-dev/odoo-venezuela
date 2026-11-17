from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestPhysicalLocationsSync(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.company.use_alternate_locations = True
        cls.env.company.physical_relocation_transfer = False
        cls.warehouse = cls.env["stock.warehouse"].create(
            {"name": "Physical Sync Warehouse", "code": "PSW"}
        )
        cls.other_warehouse = cls.env["stock.warehouse"].create(
            {"name": "Physical Sync Other Warehouse", "code": "PSO"}
        )
        cls.stock_location = cls.warehouse.lot_stock_id
        cls.location_a = cls._create_location("Shelf A", cls.stock_location)
        cls.location_b = cls._create_location("Shelf B", cls.stock_location)
        cls.other_location = cls._create_location(
            "Other Shelf", cls.other_warehouse.lot_stock_id
        )
        cls.orphan_location = cls.env["stock.location"].create(
            {"name": "Orphan Shelf", "usage": "internal"}
        )

    @classmethod
    def _create_location(cls, name, parent):
        return cls.env["stock.location"].create(
            {"name": name, "location_id": parent.id, "usage": "internal"}
        )

    def _create_template(self, locations=None, **vals):
        values = {"name": "Physical Sync Product", "type": "consu", "is_storable": True}
        if locations is not None:
            values["physical_locations_ids"] = [(6, 0, locations.ids)]
        values.update(vals)
        return self.env["product.template"].create(values)

    def _alters(self, template, active_test=True):
        return (
            self.env["stock.picking.alter.location"]
            .with_context(active_test=active_test)
            .search([("product_id", "=", template.product_variant_id.id)])
        )

    def _putaway_rules(self, template):
        return self.env["stock.putaway.rule"].search(
            [("product_id", "in", template.product_variant_ids.ids)]
        )

    def test_show_physical_locations_follows_company(self):
        template = self._create_template()
        self.assertTrue(template.show_physical_locations)
        self.env.company.use_alternate_locations = False
        template.invalidate_recordset(["show_physical_locations"])
        self.assertFalse(template.show_physical_locations)

    def test_create_with_locations_builds_alter_and_putaway(self):
        template = self._create_template(self.location_a)
        alter = self._alters(template)
        self.assertEqual(alter.pick_location, self.location_a)
        self.assertEqual(alter.warehouse_id, self.warehouse)
        rule = self._putaway_rules(template)
        self.assertEqual(rule.location_in_id, self.stock_location)
        self.assertEqual(rule.location_out_id, self.location_a)

    def test_alter_lines_built_from_existing_quants(self):
        template = self._create_template()
        variant = template.product_variant_id
        self.env["stock.quant"]._update_available_quantity(variant, self.location_a, 7.0)
        template.write({"physical_locations_ids": [(6, 0, self.location_a.ids)]})
        alter = self._alters(template)
        self.assertEqual(alter.get_line(self.location_a).available_qty, 7.0)

    def test_add_location_in_same_parent_updates_putaway_rule(self):
        template = self._create_template(self.location_a)
        template.write({"physical_locations_ids": [(4, self.location_b.id)]})
        rule = self._putaway_rules(template)
        self.assertEqual(len(rule), 1)
        self.assertEqual(rule.location_out_id, self.location_b)

    def test_remove_location_removes_putaway_rule(self):
        template = self._create_template(self.location_a | self.other_location)
        template.write({"physical_locations_ids": [(3, self.other_location.id)]})
        self.assertNotIn(self.other_location, self._putaway_rules(template).location_out_id)
        self.assertFalse(
            self._alters(template).filtered(lambda a: a.warehouse_id == self.other_warehouse)
        )

    def test_change_first_location_updates_pick_location(self):
        template = self._create_template(self.location_b)
        template.write({"physical_locations_ids": [(6, 0, (self.location_a | self.location_b).ids)]})
        self.assertEqual(self._alters(template).pick_location, self.location_a)

    def test_location_without_warehouse_is_ignored(self):
        template = self._create_template(self.orphan_location)
        self.assertFalse(self._alters(template))
        self.assertFalse(self._putaway_rules(template))

    def test_write_without_alternate_locations_skips_sync(self):
        template = self._create_template()
        self.env.company.use_alternate_locations = False
        template.write({"physical_locations_ids": [(6, 0, self.location_a.ids)]})
        self.assertFalse(self._alters(template))

    def test_create_without_alternate_locations_skips_sync(self):
        self.env.company.use_alternate_locations = False
        template = self._create_template(self.location_a)
        self.assertFalse(self._alters(template))

    def test_create_or_update_alter_location(self):
        template = self._create_template(physical_location_id=False)
        template._create_or_update_alter_location()
        self.assertFalse(self._alters(template))

        template.physical_location_id = self.orphan_location
        template._create_or_update_alter_location()
        self.assertFalse(self._alters(template))

        template.physical_location_id = self.location_a
        template._create_or_update_alter_location()
        alter = self._alters(template)
        self.assertEqual(alter.pick_location, self.location_a)

        template.physical_location_id = self.location_b
        template._create_or_update_alter_location()
        self.assertEqual(alter.pick_location, self.location_b)

    def test_create_or_update_alter_location_without_variant(self):
        template = self._create_template(physical_location_id=self.location_a.id)
        template.product_variant_ids.active = False
        template.invalidate_recordset(["product_variant_ids", "product_variant_id"])
        template._create_or_update_alter_location()
        self.assertFalse(self._alters(template, active_test=False).filtered("active"))

    def test_sync_without_variant_is_skipped(self):
        template = self._create_template()
        template.product_variant_ids.active = False
        template.invalidate_recordset(["product_variant_ids", "product_variant_id"])
        template.physical_locations_ids = [(6, 0, self.location_a.ids)]
        self.assertFalse(self._alters(template, active_test=False))

    def test_get_quants_for_alter_lines_resolves_warehouse(self):
        template = self._create_template()
        variant = template.product_variant_id
        self.env["stock.quant"]._update_available_quantity(variant, self.location_a, 3.0)
        self.env["stock.quant"]._update_available_quantity(variant, self.location_b, 2.0)
        self.env["stock.quant"].search(
            [("product_id", "=", variant.id), ("location_id", "=", self.location_b.id)]
        ).sudo().write({"reserved_quantity": 2.0})
        lines = template._get_quants_for_alter_lines(self.location_a)
        self.assertEqual(lines, [(0, 0, {"location_id": self.location_a.id, "available_qty": 3.0})])
        self.assertEqual(template._get_quants_for_alter_lines(self.orphan_location), [])

    def test_find_warehouse_from_location(self):
        template = self._create_template()
        self.assertEqual(template._find_warehouse_from_location(self.location_a), self.warehouse)
        self.assertFalse(template._find_warehouse_from_location(self.orphan_location))


@tagged("post_install", "-at_install", "l10n_ve_stock")
class TestProductTemplateTaxesAndPrices(TransactionCase):
    def _tax(self, name, amount):
        # Explicit group and country: the tests must not depend on a chart
        # of accounts being installed.
        country = self.env.company.account_fiscal_country_id or self.env.ref("base.ve")
        tax_group = self.env["account.tax.group"].create(
            {"name": "Physical Sync Taxes", "country_id": country.id}
        )
        return self.env["account.tax"].create(
            {
                "name": name,
                "amount_type": "percent",
                "amount": amount,
                "company_id": self.env.company.id,
                "tax_group_id": tax_group.id,
                "country_id": country.id,
            }
        )

    def test_write_two_taxes_raises(self):
        template = self.env["product.template"].create({"name": "Two Taxes", "type": "consu"})
        with self.assertRaises(ValidationError):
            template.write(
                {"taxes_id": [(6, 0, (self._tax("Tax A", 10) | self._tax("Tax B", 16)).ids)]}
            )

    def test_prices_with_single_tax(self):
        template = self.env["product.template"].create(
            {"name": "Single Tax", "type": "consu", "list_price": 100}
        )
        template.write({"taxes_id": [(6, 0, self._tax("Tax C", 16).ids)]})
        self.assertAlmostEqual(template.price_with_tax, 116, places=2)
        self.assertAlmostEqual(template.price_without_tax, 100, places=2)

    def test_prices_without_taxes(self):
        template = self.env["product.template"].create(
            {"name": "No Taxes", "type": "consu", "list_price": 50, "taxes_id": [(5, 0, 0)]}
        )
        self.assertEqual(template.price_with_tax, 50)
        self.assertEqual(template.price_without_tax, 50)

    def test_check_list_price_skipped_in_install_mode(self):
        template = self.env["product.template"].with_context(install_mode=True).create(
            {"name": "Install Mode Price", "type": "consu", "list_price": 0}
        )
        self.assertEqual(template.list_price, 0)

    def test_available_quantity_ignores_quants_outside_stock(self):
        self.env.company.use_free_qty_odoo = False
        warehouse = self.env["stock.warehouse"].create({"name": "Qty Warehouse", "code": "QTW"})
        template = self.env["product.template"].create(
            {"name": "Qty Outside Stock", "type": "consu", "is_storable": True}
        )
        variant = template.product_variant_id
        quants = self.env["stock.quant"]
        quants._update_available_quantity(variant, warehouse.lot_stock_id, 4.0)
        quants._update_available_quantity(variant, warehouse.wh_output_stock_loc_id, 6.0)
        template._compute_available_quantity()
        self.assertEqual(template.quantity, 4.0)
