from odoo import models, fields, api, _
class Warehouse(models.Model):
    _inherit = "stock.warehouse"

    def _get_picking_type_create_values(self, max_sequence):
        
        res , new_max_sequence = super()._get_picking_type_create_values(max_sequence)

        res['in_type_id']['name'] = _('Receipts')
        res['out_type_id']['name'] = _('Delivery Orders')
        res['pack_type_id']['name'] = _('Pack')
        res['pick_type_id']['name'] = _('Pick')
        res['int_type_id']['name'] = _('Internal Transfers')

        return res, new_max_sequence