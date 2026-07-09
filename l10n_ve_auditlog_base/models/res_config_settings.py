from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    log_outgoing_requests = fields.Selection(
        related="company_id.log_outgoing_requests", readonly=False
    )
