from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

import logging

_logger = logging.getLogger(__name__)


class AppointmentType(models.Model):
    _inherit = "appointment.type"

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for appointment in res:
            if appointment.question_ids:
                appointment._count_show_question_in_calendar()
        return res

    def write(self, vals):
        res = super().write(vals)
        if "question_ids" in vals:
            for appointment in self:
                appointment._count_show_question_in_calendar()
        return res

    def _count_show_question_in_calendar(self):
        count_required = 0
        for question in self.question_ids:
            count_required += 1 if question.show_in_calendar else 0
        if count_required > 1:
            raise ValidationError(
                _("You cannot add more than one question to be displayed on the calendar.")
            )
