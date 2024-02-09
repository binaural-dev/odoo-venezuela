from odoo import _, api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    pos_discount_require_supervisor_key = fields.Boolean()
    pos_refund_require_supervisor_key = fields.Boolean()
    pos_close_session_require_supervisor_key = fields.Boolean()
    pos_remove_orderline_require_supervisor_key = fields.Boolean()
    pos_change_receipt_require_supervisor_key = fields.Boolean()
    pos_cashmove_require_supervisor_key = fields.Boolean()
