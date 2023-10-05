from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    role_picking = fields.Selection(related="user_id.role_picking", readonly=False)

    supervisor_barcode_password = fields.Char(
        related="user_id.supervisor_barcode_password", readonly=False
    )
    pick_ids = fields.One2many(
        "stock.picking", "picker_id", domain=[("operation_state", "in", ["ready","in_process","paused"])]
    )

    def available_to_assing_picking(self):
        """
        This function checks if the picker is available to be assigned a pick, checking if it is
        not in a pick in progress
        """
        if len(self.pick_ids.filtered(lambda x: x.operation_state in ["ready", "in_process"])) == 0:
            return True
        return False
