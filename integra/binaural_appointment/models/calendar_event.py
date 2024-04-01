from odoo import api, fields, models, Command

import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)

class CalendarEventCrm(models.Model):
    _inherit = 'calendar.event'

    def _create_lead_from_appointment(self):
        leads = super()._create_lead_from_appointment()

        for event, lead in zip(self, leads):
            lead.product_id = event.appointment_type_id.product_id
            lead.start = self.start - timedelta(hours=4)
        return leads