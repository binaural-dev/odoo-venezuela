from odoo import api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    role_picking = fields.Selection(related="user_id.role_picking", readonly=False)

    password_stock_barcode = fields.Char()

    @api.onchange("password_stock_barcode")
    def _onchange_type_job(self):
        if self.type_job != "supervisor":
            raise ValidationError("Only supervisor can contain password")
