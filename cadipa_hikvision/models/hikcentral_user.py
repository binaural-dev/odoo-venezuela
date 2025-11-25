from odoo import models, api, exceptions, fields, _
from odoo.exceptions import ValidationError
import qrcode
from dateutil.relativedelta import relativedelta
import io
import base64
import logging
from odoo.addons.binaural_hikvision.services import hikcentral_api

_logger = logging.getLogger(__name__)


class AppointmentGuests(models.Model):
    _inherit = "hikcentral.users"

    comes_from_calendar_reservation = fields.Boolean()
    
    event_id = fields.Many2one(
        "calendar.event",
        string="Event",
        ondelete="cascade",
    )

    appointment_guest_id = fields.Many2one(
        "appointment.guests",
    )
