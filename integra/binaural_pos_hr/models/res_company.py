from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    pos_require_supervisor_key = fields.Boolean("Supervisor Key")
