from odoo import _, api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    pos_employee_type = fields.Selection(
        [
            ("cashier", "Cashier"),
            ("supervisor", "Supervisor"),
            ("waiter", "Waiter"),
        ],
        default="cashier",
    )
