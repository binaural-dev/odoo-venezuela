import re
from odoo import api, fields, models, _
from zoneinfo import ZoneInfo
from odoo.exceptions import UserError, ValidationError


import logging

_logger = logging.getLogger(__name__)


class HikcentralVisitorAppointment(models.Model):
    _inherit = "hikcentral.visitor.appointment"


    calendar_event_ids = fields.Many2many(
        "calendar.event",
        string="Eventos de Calendario Origen"
    )