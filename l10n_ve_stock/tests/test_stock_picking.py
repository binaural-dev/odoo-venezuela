from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError
from odoo import Command


@tagged('post_install', '-at_install', "l10n_ve_stock")
class TestStockPickingPhysicalAddress(TransactionCase):

    def setUp(self):
        super().setUp()
        self.warehouse_a = self.env['stock.warehouse'].create({
            'name': 'Test WH A',
            'code': 'TWHA',
            'physical_address': 'Av. Principal, Zona Industrial, Caracas',
        })
        self.warehouse_b = self.env['stock.warehouse'].create({
            'name': 'Test WH B',
            'code': 'TWHB',
            'physical_address': 'Calle 5, Urbanización El Viñedo, Valencia',
        })
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'consu',
            'is_storable': True,
        })

    def _get_internal_picking_type(self, warehouse):
        internal_type = warehouse.int_type_id
        if not internal_type or not internal_type.exists():
            internal_type = self.env['stock.picking.type'].search([
                ('warehouse_id', '=', warehouse.id),
                ('code', '=', 'internal'),
            ], limit=1)
        if not internal_type:
            internal_type = self.env['stock.picking.type'].create({
                'name': 'Test Internal Transfers',
                'code': 'internal',
                'warehouse_id': warehouse.id,
            })
        return internal_type

    def test_physical_addresses_between_warehouses(self):
        picking_type = self._get_internal_picking_type(self.warehouse_a)
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.warehouse_a.lot_stock_id.id,
            'location_dest_id': self.warehouse_b.lot_stock_id.id,
            'move_ids': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        })
        self.assertEqual(
            picking.source_physical_address,
            'Av. Principal, Zona Industrial, Caracas'
        )
        self.assertEqual(
            picking.destination_physical_address,
            'Calle 5, Urbanización El Viñedo, Valencia'
        )

    def test_physical_address_false_for_non_warehouse_location(self):
        customer_loc = self.env.ref('stock.stock_location_customers')
        picking_type = self._get_internal_picking_type(self.warehouse_a)
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.warehouse_a.lot_stock_id.id,
            'location_dest_id': customer_loc.id,
            'move_ids': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        })
        self.assertEqual(
            picking.source_physical_address,
            'Av. Principal, Zona Industrial, Caracas'
        )
        self.assertFalse(picking.destination_physical_address)

    def test_physical_address_recomputes_on_location_change(self):
        picking_type = self._get_internal_picking_type(self.warehouse_a)
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.warehouse_a.lot_stock_id.id,
            'location_dest_id': self.warehouse_b.lot_stock_id.id,
            'move_ids': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        })
        self.assertEqual(
            picking.source_physical_address,
            'Av. Principal, Zona Industrial, Caracas'
        )
        picking.write({'location_dest_id': self.warehouse_a.lot_stock_id.id})
        self.assertEqual(
            picking.destination_physical_address,
            'Av. Principal, Zona Industrial, Caracas'
        )
        self.assertEqual(
            picking.source_physical_address,
            'Av. Principal, Zona Industrial, Caracas'
        )

@tagged('post_install', '-at_install', "l10n_ve_stock")
class TestStockPickingActionPickingDeliveryType(TransactionCase):

    def setUp(self):
        super().setUp()
        self.warehouse = self.env['stock.warehouse'].search([], limit=1)
        self.partner = self.env['res.partner'].create({'name': 'Cliente Test'})
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'consu',
            'is_storable': True,
        })
        self.picking_type = self.warehouse.out_type_id
        self.customer_loc = self.env.ref('stock.stock_location_customers')

        self.reference = self.env['stock.reference'].create({'name': 'REF-TEST-001'})

        self.picking1 = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': self.picking_type.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.customer_loc.id,
            'move_ids': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'reference_ids': [Command.set(self.reference.ids)],
            })],
        })
        self.picking2 = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': self.picking_type.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.customer_loc.id,
            'move_ids': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'reference_ids': [Command.set(self.reference.ids)],
            })],
        })

    def test_action_with_multiple_pickings(self):
        picking3 = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': self.picking_type.id,
            'location_id': self.warehouse.lot_stock_id.id,
            'location_dest_id': self.customer_loc.id,
            'move_ids': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'reference_ids': [Command.set(self.reference.ids)],
            })],
        })
        action = self.picking1._get_action_picking_delivery_type('out')
        self.assertIn('domain', action)
        domain = action['domain']
        if isinstance(domain, str):
            self.assertIn(str(self.picking2.id), domain)
            self.assertIn(str(picking3.id), domain)
            self.assertNotIn(str(self.picking1.id), domain)
        else:
            ids = domain[0][2]
            self.assertIn(self.picking2.id, ids)
            self.assertIn(picking3.id, ids)
            self.assertNotIn(self.picking1.id, ids)

    def test_action_with_single_picking(self):
        action = self.picking1._get_action_picking_delivery_type('out')
        self.assertIn('res_id', action)
        self.assertEqual(action['res_id'], self.picking2.id)

    def test_action_no_pickings_raises(self):
        self.picking2.unlink()
        self.picking1.move_ids.reference_ids = [Command.clear()]
        with self.assertRaises(UserError):
            self.picking1._get_action_picking_delivery_type('out')
