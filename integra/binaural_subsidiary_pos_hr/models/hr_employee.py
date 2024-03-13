from odoo import _, api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    subsidiary_id = fields.Many2one(related="user_id.subsidiary_id")

    subsidiary_ids = fields.Many2many(related="user_id.subsidiary_ids")

    is_required_subsidiary = fields.Boolean(related="user_id.is_required_subsidiary")

    
    def get_pos_hr_employee_fields(self):
        fields = super().get_pos_hr_employee_fields()

        fields.extend([
            "subsidiary_id",
            "subsidiary_ids",
            "is_required_subsidiary"
        ])

        return fields
