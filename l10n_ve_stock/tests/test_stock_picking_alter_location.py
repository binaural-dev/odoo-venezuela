from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install', 'stock_picking_alter_location')
class TestStockPickingAlterLocation(TransactionCase):
    def setUp(self):
        super().setUp()

        self.env.company.use_alternate_locations = True
        self.category = self.env.ref('product.product_category_all')
        self.partner = self.env['res.partner'].create({'name': 'Proveedor de prueba'})

        self.warehouse = self.env['stock.warehouse'].create({
            'name': 'Alternate Locations Warehouse',
            'code': 'ALW',
            'partner_id': self.partner.id,
        })
        self.location = self.warehouse.lot_stock_id

    def _create_product(self, name, physical_location=None):
        vals = {
            'name': name,
            'type': 'consu',
            'is_storable': True,
            'categ_id': self.category.id,
        }
        if physical_location is not None:
            vals['physical_location_id'] = physical_location.id
            vals['physical_locations_ids'] = [(6, 0, [physical_location.id])]
        return self.env['product.template'].create(vals)

    def test_receipt_with_backorder_increments_alter_location_once(self):
        """Backorder wizard confirmation must not duplicate the increment
        of stock.picking.alter.location.line (the hook ran before super())."""
        product_tmpl = self._create_product('Product with physical location', self.location)
        product_variant = product_tmpl.product_variant_id

        alter_location = self.env['stock.picking.alter.location'].search([
            ('product_id', '=', product_variant.id),
        ], limit=1)
        self.assertTrue(alter_location)

        picking = self.env['stock.picking'].create({
            'picking_type_id': self.warehouse.in_type_id.id,
            'partner_id': self.partner.id,
            'location_id': self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': self.location.id,
            'move_ids_without_package': [(0, 0, {
                'name': product_variant.name,
                'product_id': product_variant.id,
                'product_uom_qty': 20,
                'product_uom': product_variant.uom_id.id,
                'location_id': self.env.ref('stock.stock_location_suppliers').id,
                'location_dest_id': self.location.id,
            })],
        })
        picking.action_confirm()
        picking.move_line_ids.quantity = 12

        res = picking.button_validate()
        self.assertIsInstance(res, dict)
        self.assertEqual(res.get('res_model'), 'stock.backorder.confirmation')

        pick_line = alter_location.stock_alter_location_lines.filtered(
            lambda l: l.location_id == alter_location.pick_location
        )
        self.assertEqual(
            sum(pick_line.mapped('available_qty')), 0,
            "Must not increment before confirming the backorder wizard",
        )

        wizard = self.env['stock.backorder.confirmation'].with_context(**res['context']).create({})
        wizard.process()

        pick_line = alter_location.stock_alter_location_lines.filtered(
            lambda l: l.location_id == alter_location.pick_location
        )
        self.assertEqual(
            sum(pick_line.mapped('available_qty')), 12,
            "The increment must be applied only once, with the actually received quantity",
        )

    def test_create_multi_records_with_mixed_physical_location(self):
        """create_multi with a product that has explicit physical_location_id and another
        that does not, must not break with ensure_one() nor generate an alternate location for the one without it."""
        tmpl_with_location = self._create_product('Product with explicit location', self.location)
        tmpl_without_location = self.env['product.template'].create({
            'name': 'Product without explicit location',
            'type': 'consu',
            'is_storable': True,
            'categ_id': self.category.id,
        })

        alter_location_with = self.env['stock.picking.alter.location'].search([
            ('product_id', '=', tmpl_with_location.product_variant_id.id),
        ])
        alter_location_without = self.env['stock.picking.alter.location'].search([
            ('product_id', '=', tmpl_without_location.product_variant_id.id),
        ])

        self.assertTrue(alter_location_with)
        self.assertFalse(alter_location_without)

    def test_subtract_physical_quantity_ignores_output_location(self):
        """subtract_physical_quantity() must not deduct from pick_location the quantities
        that are in Output (different scopes: total_alter_quantity excludes them, quant_total should not)."""
        product_tmpl = self._create_product('Product with output delivery', self.location)
        product_variant = product_tmpl.product_variant_id

        alter_location = self.env['stock.picking.alter.location'].search([
            ('product_id', '=', product_variant.id),
        ], limit=1)
        output_location = self.warehouse.wh_output_stock_loc_id

        self.env['stock.quant']._update_available_quantity(product_variant, self.location, 15.0)
        self.env['stock.quant']._update_available_quantity(product_variant, output_location, 5.0)

        alter_location.subtract_physical_quantity()

        pick_line = alter_location.stock_alter_location_lines.filtered(
            lambda l: l.location_id == alter_location.pick_location
        )
        self.assertEqual(
            sum(pick_line.mapped('available_qty')), 15.0,
            "The pick_location line must not be affected by the quantity in Output",
        )

    def test_remove_physical_location_archives_alter_location(self):
        """When removing a physical location from the m2m, the alter_location of the warehouse
        must be archived if no location of that warehouse remains."""
        product_tmpl = self._create_product('Product to archive', self.location)
        product_variant = product_tmpl.product_variant_id

        alter_location = self.env['stock.picking.alter.location'].search([
            ('product_id', '=', product_variant.id),
            ('warehouse_id', '=', self.warehouse.id),
        ], limit=1)
        self.assertTrue(alter_location)
        self.assertTrue(alter_location.active)

        product_tmpl.write({'physical_locations_ids': [(5, 0, 0)]})

        self.assertFalse(
            alter_location.active,
            "The alter_location must be archived when removing the physical location",
        )

    def test_readd_physical_location_reactivates_alter_location(self):
        """When re-adding a location of an archived warehouse, the existing
        alter_location must be reactivated instead of creating a duplicate."""
        product_tmpl = self._create_product('Product to reactivate', self.location)
        product_variant = product_tmpl.product_variant_id

        alter_location = self.env['stock.picking.alter.location'].search([
            ('product_id', '=', product_variant.id),
            ('warehouse_id', '=', self.warehouse.id),
        ], limit=1)
        self.assertTrue(alter_location)
        original_id = alter_location.id

        product_tmpl.write({'physical_locations_ids': [(5, 0, 0)]})
        self.assertFalse(alter_location.active)

        product_tmpl.write({'physical_locations_ids': [(4, self.location.id, 0)]})

        reactivated = self.env['stock.picking.alter.location'].search([
            ('product_id', '=', product_variant.id),
            ('warehouse_id', '=', self.warehouse.id),
        ], limit=1)
        self.assertTrue(reactivated.active)
        self.assertEqual(
            reactivated.id, original_id,
            "Must reactivate the same alter_location, not create a new one",
        )