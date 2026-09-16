from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    log_outgoing_requests = fields.Selection(
        related="company_id.log_outgoing_requests", readonly=False
    )
    response_body_max_chars = fields.Integer(
        related="company_id.response_body_max_chars", readonly=False
    )
