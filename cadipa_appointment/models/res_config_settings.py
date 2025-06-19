from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    appointment_open_hour = fields.Selection(
        related='company_id.appointment_open_hour',
        readonly=False
    )

    appointment_close_hour = fields.Selection(
        related='company_id.appointment_close_hour',
        readonly=False
    )
