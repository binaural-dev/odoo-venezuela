from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = "res.users"

    role_picking = fields.Selection(
        [
            ("picker", "Role Picker"),
            ("packer", "Role Packer"),
            ("out", "Role Checker"),
            ("supervisor", "Role Supervisor"),
        ],
        default=False,
    )
    supervisor_barcode_password = fields.Char(string="Supervisor Barcode Password")

    def check_password_supervisor(self, password):
        """
        Validate if the password is correct for the supervisor
        """
        return self.supervisor_barcode_password == password
