from odoo.addons.appointment.controllers.portal import AppointmentPortal

from odoo.http import request, route

import logging

_logger = logging.getLogger(__name__)


class CadipaAppointmentPortal(AppointmentPortal):

    def _get_portal_default_domain(self):
        domain = super(CadipaAppointmentPortal, self)._get_portal_default_domain()

        partner = request.env.user.partner_id
        booker_condition = [("appointment_booker_id", "=", partner.id)]

        if domain:
            return ["|"] + domain + booker_condition

        return booker_condition
