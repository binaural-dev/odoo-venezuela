from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    role_picking = fields.Selection(related="user_id.role_picking", readonly=False)

    supervisor_barcode_password = fields.Char(
        related="user_id.supervisor_barcode_password", readonly=False
    )
