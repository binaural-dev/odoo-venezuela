from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    pos_discount_require_supervisor_key = fields.Boolean(
        related="pos_config_id.pos_discount_require_supervisor_key", readonly=False
    )
    pos_refund_require_supervisor_key = fields.Boolean(
        related="pos_config_id.pos_refund_require_supervisor_key", readonly=False
    )
    pos_close_session_require_supervisor_key = fields.Boolean(
        related="pos_config_id.pos_close_session_require_supervisor_key", readonly=False
    )
    pos_type_close_require_supervisor_key = fields.Selection(
        selection=[("button", "Button"), ("popup", "Popup")],
        related="pos_config_id.pos_type_close_require_supervisor_key", readonly=False
    )
    pos_remove_orderline_require_supervisor_key = fields.Boolean(
        related="pos_config_id.pos_remove_orderline_require_supervisor_key", readonly=False
    )
    pos_change_receipt_require_supervisor_key = fields.Boolean(
        related="pos_config_id.pos_change_receipt_require_supervisor_key", readonly=False
    )
    pos_cashmove_require_supervisor_key = fields.Boolean(
        related="pos_config_id.pos_cashmove_require_supervisor_key", readonly=False
    )
