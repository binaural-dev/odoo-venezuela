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

    minimum_child_age = fields.Integer(
        related='company_id.minimum_child_age',
        readonly=False,
    )

    maximum_child_age = fields.Integer(
        related='company_id.maximum_child_age',
        readonly=False,
    )

    membership_auto_suspend = fields.Boolean(
        related='company_id.membership_auto_suspend',
        readonly=False,
    )
    membership_suspension_delay_days = fields.Integer(
        related='company_id.membership_suspension_delay_days',
        readonly=False,
    )
