from odoo import api, fields, models


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
