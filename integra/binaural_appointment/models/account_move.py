from odoo import api, fields, models


class ModelName(models.Model):
    _inherit = 'account.move'

    calendar_event_id = fields.Many2one(
        "calendar.event",
        string='Calendar Event',
    )
