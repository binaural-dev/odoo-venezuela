from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError
from odoo import Command

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
