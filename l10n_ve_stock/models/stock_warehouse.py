from odoo import models, fields, api, _


class Warehouse(models.Model):
    _inherit = "stock.warehouse"

    def _get_picking_type_create_values(self, max_sequence):
        """ When a warehouse is created this method return the values needed in
        order to create the new picking types for this warehouse. Every picking
        type are created at the same time than the warehouse howver they are
        activated or archived depending the delivery_steps or reception_steps.
        """
        input_loc, output_loc = self._get_input_output_locations(self.reception_steps, self.delivery_steps)
        return {
            'in_type_id': {
                'name': _('Receipts'),
                'code': 'incoming',
                'use_existing_lots': False,
                'default_location_src_id': False,
                'sequence': max_sequence + 1,
                'show_reserved': False,
                'sequence_code': 'IN',
                'company_id': self.company_id.id,
            }, 'out_type_id': {
                'name': _('Delivery Orders'),
                'code': 'outgoing',
                'use_create_lots': False,
                'default_location_dest_id': False,
                'sequence': max_sequence + 5,
                'sequence_code': 'OUT',
                'print_label': True,
                'company_id': self.company_id.id,
            }, 'pack_type_id': {
                'name': _('Pack'),
                'code': 'internal',
                'use_create_lots': False,
                'use_existing_lots': True,
                'default_location_src_id': self.wh_pack_stock_loc_id.id,
                'default_location_dest_id': output_loc.id,
                'sequence': max_sequence + 4,
                'sequence_code': 'PACK',
                'company_id': self.company_id.id,
            }, 'pick_type_id': {
                'name': _('Pick'),
                'code': 'internal',
                'use_create_lots': False,
                'use_existing_lots': True,
                'default_location_src_id': self.lot_stock_id.id,
                'sequence': max_sequence + 3,
                'sequence_code': 'PICK',
                'company_id': self.company_id.id,
            }, 'int_type_id': {
                'name': _('Internal Transfers'),
                'code': 'internal',
                'use_create_lots': False,
                'use_existing_lots': True,
                'default_location_src_id': self.lot_stock_id.id,
                'default_location_dest_id': self.lot_stock_id.id,
                'active': self.reception_steps != 'one_step' or self.delivery_steps != 'ship_only' or self.env.user.has_group('stock.group_stock_multi_locations'),
                'sequence': max_sequence + 2,
                'sequence_code': 'INT',
                'company_id': self.company_id.id,
            },
        }, max_sequence + 6