from odoo import fields, models
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    role_picking = fields.Selection(
        [
            ("picker", "Picker"),
            ("packer", "Packer"),
            ("out", "checker"),
            ("supervisor", "Supervisor"),
        ],
        default=False,
    )
    supervisor_barcode_password = fields.Char(string="Supervisor Barcode Password")

    def check_password_supervisor(self, password):
        if self.supervisor_barcode_password == password:
            return True
        return False

    def available_to_assing_picking(self):
        """
        This function checks if the picker is available to be assigned a pick, checking if it is
        not in a pick in progress
        """
        if (
            self.env["stock.picking"].search_count(
                [
                    ("picker_id", "=", self.id),
                    ("operation_state", "in", ["ready", "in_process"]),
                ]
            )
            == 0
        ):
            return True
        return False
