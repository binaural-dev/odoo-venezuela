from odoo.addons.appointment.controllers.portal import AppointmentPortal

from odoo.http import request, route
from odoo.osv import expression

import logging

_logger = logging.getLogger(__name__)


class CadipaAppointmentPortal(AppointmentPortal):

    def _get_portal_default_domain(self):
        domain = super(CadipaAppointmentPortal, self)._get_portal_default_domain()

        partner = request.env.user.partner_id
        booker_condition = [("appointment_booker_id", "=", partner.id)]
        partner_main_condition = [("partner_id", "=", partner.id)]

        if domain:
            return expression.OR([domain, booker_condition, partner_main_condition])

        return expression.OR([booker_condition, partner_main_condition])
