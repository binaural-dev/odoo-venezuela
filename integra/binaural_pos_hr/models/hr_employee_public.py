from odoo import _, api, fields, models


class HrEmployeePublic(models.Model):
    _inherit = 'hr.employee.public'

    pos_employee_type = fields.Selection(
        [
            ("cashier", "Cashier"),
            ("supervisor", "Supervisor"),
            ("waiter", "Waiter"),
        ],
        default="cashier",
    )
