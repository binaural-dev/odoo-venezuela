from odoo import _, api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    pos_require_supervisor_key = fields.Boolean(related="company_id.pos_require_supervisor_key")
