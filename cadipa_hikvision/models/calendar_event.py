from setuptools import Command
from odoo import models, fields, _, Command
import logging

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    hikcentral_appointment_id = fields.Many2one(
        "hikcentral.visitor.appointment",
        string="Cita de Visitante HikCentral",
        copy=False,
        readonly=True,
    )

    guest_ids = fields.Many2many(
        "appointment.guests",
        string="Invitados (Appointment Guests)",
    )

    def _create_hikcentral_visitor_appointment(self):
        """
        Creates a single 'hikcentral.visitor.appointment' for a group of events
        that share the same access_token, covering the full time range.
        """
        if not self:
            return


        events_by_token = {}
        for event in self:
            if event.access_token:
                events_by_token.setdefault(
                    event.access_token, self.env["calendar.event"]
                )
                events_by_token[event.access_token] |= event

        for access_token, event_group in events_by_token.items():
            primary_event = event_group[0]
            if not primary_event.guest_ids:
                _logger.info(
                    "Event group with token %s skipped: no guests found.",
                    access_token,
                )
                continue

            if any(event.hikcentral_appointment_id for event in event_group):
                _logger.info(
                    "Event group with token %s has already been processed.", access_token
                )
                continue

            try:
                hik_host = self.env["hikcentral.users"].search(
                    [("partner_id", "=", primary_event.appointment_booker_id.id)], limit=1
                )
                if not hik_host:
                    primary_event.message_post(
                        body="Host not found in HikCentral. Cannot create the appointment."
                    )
                    continue

                start_date = min(event_group.mapped("start"))
                end_date = max(event_group.mapped("stop"))

                visitor_lines_vals = []
                for guest in primary_event.guest_ids:
                    name_parts = (guest.name or "Invitado").split(" ", 1)
                    certificate_no = (
                        f"{guest.prefix_vat}{guest.vat}"
                        if guest.prefix_vat and guest.vat
                        else f"odooguest{guest.id}"
                    )

                    visitor_lines_vals.append(
                        (
                            0,
                            0,
                            {
                                "first_name": name_parts[0],
                                "last_name": (
                                    name_parts[1] if len(name_parts) > 1 else " "
                                ),
                                "certificate_no": certificate_no,
                                "email": guest.email,
                            },
                        )
                    )

                if not visitor_lines_vals:
                    continue
                

                appointment_record = self.env["hikcentral.visitor.appointment"].create(
                    {
                        "calendar_event_ids": [Command.set(event_group.ids)],
                        "receptionist_id": hik_host.id,
                        "start_time": start_date,
                        "end_time": end_date,
                        "visitor_info_ids": visitor_lines_vals,
                    }
                )

                event_group.write({"hikcentral_appointment_id": appointment_record.id})

                primary_event.message_post(
                    body=_(
                        "Visitor appointment record for HikCentral (ID: %s) created for the group. Starting synchronization..."
                    )
                    % appointment_record.id
                )

                appointment_record.action_send_to_hikcentral(auto_send_invitations=True)

            except Exception as e:
                error_msg = (
                    _("Failed to process the appointment group for HikCentral: %s") % e
                )
                primary_event.message_post(body=error_msg)
                _logger.exception(
                    "Error in _create_hikcentral_visitor_appointment for group with token %s",
                    access_token,
                )
