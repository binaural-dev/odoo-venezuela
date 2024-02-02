from odoo import fields, models


class ResourceCalendarAttendance(models.Model):
    _inherit = "resource.calendar.attendance"

    day_period = fields.Selection(
        selection_add=[("night", "Night"), ("early_morning", "Early Morning")],
        ondelete={"night": "set default", "early_morning": "set default"},
    )
