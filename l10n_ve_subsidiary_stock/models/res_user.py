from odoo import _, api, fields, models


class ResUsers(models.Model):
    _inherit = "res.users"

    can_transfer_to_warehouses_without_branch = fields.Boolean()
