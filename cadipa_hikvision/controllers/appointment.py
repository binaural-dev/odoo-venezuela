import logging

from odoo.addons.cadipa_appointment.controllers.appointment import (
    AppointmentControllerMulti,
)

_logger = logging.getLogger(__name__)


class CadipaWebsiteAppointment(AppointmentControllerMulti):

    def _post_submission_hook(self, created_events):
        """
        Sobrescribe el hook del padre para disparar la sincronización
        con HikCentral para los eventos recién creados.
        """
        super(CadipaWebsiteAppointment, self)._post_submission_hook(created_events)
                
        if created_events:
            try:
                created_events._create_hikcentral_visitor_appointment()
            except Exception as e:
                _logger.error(
                    "Failed to initiate synchronization with HikCentral from the hook: %s",
                    e,
                )