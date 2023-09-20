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

    def available_to_assing_picking(self):
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
