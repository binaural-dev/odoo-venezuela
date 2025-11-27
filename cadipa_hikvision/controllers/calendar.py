from odoo import http
from odoo.http import request
import logging

from odoo.addons.appointment.controllers.calendar import AppointmentCalendarController

_logger = logging.getLogger(__name__)


class HikvisionAppointmentCancel(AppointmentCalendarController):

    @http.route()
    def appointment_cancel(self, access_token, partner_id, **kwargs):
        """
        Clean up HikCentral guests accesses for the associated event.
        """
        
        try:
            event = (
                request.env["calendar.event"]
                .sudo()
                .search([("access_token", "=", access_token)], limit=1)
            )
            if event:
                _logger.info(
                    f"Processing HikCentral cancellation for event: {event.name} (ID: {event.id})"
                )

                hik_users = (
                    request.env["hikcentral.users"]
                    .sudo()
                    .search(
                        [
                            ("event_id", "=", event.id),
                        ]
                    )
                )

                if hik_users:
                    _logger.info(f"Found {len(hik_users)} users to delete.")
                    for user in hik_users:
                        try:
                            user.action_delete_from_hikcentral()
                            user.action_send_cancellation_email()
                        except Exception as e:
                            _logger.error(f"Failed to delete HikUser {user.id}: {e}")

                    _logger.info("HikCentral cancellation process finished.")
                else:
                    _logger.info("No active HikCentral users found for this event.")

        except Exception as e:
            _logger.exception(
                "Critical error cancelling HikCentral accesses: %s",
                e,
            )

        return super().appointment_cancel(access_token, partner_id, **kwargs)
