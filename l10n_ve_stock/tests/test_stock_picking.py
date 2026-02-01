from odoo.tests import TransactionCase, tagged
from odoo.exceptions import UserError

@tagged('post_install', '-at_install', "l10n_ve_stock")
class TestStockPickingActionPickingDeliveryType(TransactionCase):

    def setUp(self):
        super().setUp()
        self.partner = self.env['res.partner'].create({'name': 'Cliente Test'})
        self.picking_type = self.env['stock.picking.type'].create({
            'name': 'Delivery OUT',
            'code': 'outgoing',
            'sequence_code': 'OUT'
        })
        self.group = self.env['procurement.group'].create({'name': 'Grupo Test'})
        self.picking1 = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'group_id': self.group.id,
            'picking_type_id': self.picking_type.id,
            'type_delivery_step': 'out',
            'name': 'Picking 1',
        })
        self.picking2 = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'group_id': self.group.id,
            'picking_type_id': self.picking_type.id,
            'type_delivery_step': 'out',
            'name': 'Picking 2',
        })
            
    def test_action_with_multiple_pickings(self):
        self.env['stock.picking'].search([('group_id', '=', self.group.id), ('type_delivery_step', '=', 'out')])
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
        self.picking1.group_id = False
        with self.assertRaises(UserError):
            self.picking1._get_action_picking_delivery_type('out')