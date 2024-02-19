
import hashlib

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

    def get_pos_hr_employee_domain(self):
        return [
            ('pos_employee_type', '=', 'supervisor')
        ]
    
    def get_pos_hr_employee_fields(self):
        return ['name', 'pos_employee_type', 'pin', 'barcode']

    @api.model
    def get_pos_hr_employee(self):
        domain = self.get_pos_hr_employee_domain()
        fields = self.get_pos_hr_employee_fields()

        hr_employee_ids = self.sudo().search_read(domain, fields)

        for e in hr_employee_ids:
            e['barcode'] = hashlib.sha1(e['barcode'].encode('utf8')).hexdigest() if e['barcode'] else False
            e['pin'] = hashlib.sha1(e['pin'].encode('utf8')).hexdigest() if e['pin'] else False

        return hr_employee_ids