from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class AppointmentQuestion(models.Model):
    _inherit = "appointment.question"

    show_in_calendar = fields.Boolean()
