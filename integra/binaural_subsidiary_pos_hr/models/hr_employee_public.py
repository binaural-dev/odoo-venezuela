from odoo import _, api, fields, models


class HrEmployeePublic(models.Model):
    _inherit = "hr.employee.public"

    subsidiary_id = fields.Many2one(related="user_id.subsidiary_id")

    subsidiary_ids = fields.Many2many(related="user_id.subsidiary_ids")

    is_required_subsidiary = fields.Boolean(related="user_id.is_required_subsidiary")

