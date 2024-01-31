from odoo import _, api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    pos_discount_require_supervisor_key = fields.Boolean(related="company_id.pos_discount_require_supervisor_key")
    pos_refund_require_supervisor_key = fields.Boolean(related="company_id.pos_refund_require_supervisor_key")
