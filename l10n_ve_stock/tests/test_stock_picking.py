from odoo import Command
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError

@tagged('post_install', '-at_install', "l10n_ve_stock")
class TestStockPickingActionPickingDeliveryType(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'Cliente Test'})
        self.picking_type = self.env.ref('stock.picking_type_out')
        self.uom_unit = self.env.ref('uom.product_uom_unit')
        self.product = self.env['product.product'].create({
            'name': 'Producto Test',
            'type': 'consu',
            'uom_id': self.uom_unit.id,
        })
        self.reference = self.env['stock.reference'].create({'name': 'REF-TEST'})
        self.picking1 = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': self.picking_type.id,
            'name': 'Picking 1',
            'move_ids': [Command.create({
                'name': 'Move 1',
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'product_uom': self.uom_unit.id,
                'location_id': self.picking_type.default_location_src_id.id,
                'location_dest_id': self.picking_type.default_location_dest_id.id,
                'reference_ids': [Command.link(self.reference.id)],
            })],
        })
        self.picking2 = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': self.picking_type.id,
            'name': 'Picking 2',
            'move_ids': [Command.create({
                'name': 'Move 2',
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'product_uom': self.uom_unit.id,
                'location_id': self.picking_type.default_location_src_id.id,
                'location_dest_id': self.picking_type.default_location_dest_id.id,
                'reference_ids': [Command.link(self.reference.id)],
            })],
        })
            
    def test_action_with_multiple_pickings(self):
        action = self.picking1._get_action_picking_delivery_type('out')
        self.assertIn('domain', action)
        self.assertIn(self.picking2.id, [id for id in action['domain'][0][2]])
        self.assertNotIn(self.picking1.id, [id for id in action['domain'][0][2]])

    def test_action_with_single_picking(self):
       self.picking2.unlink()
       with self.assertRaises(UserError):
           self.picking1._get_action_picking_delivery_type('out')

    def test_action_no_pickings_raises(self):
       # Sin pickings relacionados, debe lanzar UserError
        self.picking1.move_ids.reference_ids = [Command.clear()]
        with self.assertRaises(UserError):
            self.picking1._get_action_picking_delivery_type('out')
