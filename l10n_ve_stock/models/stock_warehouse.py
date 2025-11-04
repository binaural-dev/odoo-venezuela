from odoo import models, fields, api, _
from odoo.exceptions import UserError

class Warehouse(models.Model):
    _inherit = "stock.warehouse"

    def _get_picking_type_create_values(self, max_sequence):
        """ When a warehouse is created this method return the values needed in
        order to create the new picking types for this warehouse. Every picking
        type are created at the same time than the warehouse howver they are
        activated or archived depending the delivery_steps or reception_steps.
        """
        #raise ("DeprecationWarning", "_get_picking_type_create_values is deprecated in Odoo 19.0, use _get_picking_type_create_values_and_sequence instead.")
        #input_loc, output_loc = self._get_input_output_locations(self.reception_steps, self.delivery_steps)
        res = super()._get_picking_type_create_values(max_sequence)
        return res
