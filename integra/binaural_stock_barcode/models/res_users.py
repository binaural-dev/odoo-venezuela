from odoo import api, fields, models
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
        """
        Validate if the password is correct for the supervisor
        """
        if self.supervisor_barcode_password == password:
            return True
        return False
