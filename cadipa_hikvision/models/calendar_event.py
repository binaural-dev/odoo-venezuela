from datetime import timedelta
from odoo import models, fields, _, Command
import logging
from odoo.tools.image import image_data_uri

_logger = logging.getLogger(__name__)


class CalendarEvent(models.Model):
    _inherit = "calendar.event"

    hikcentral_synced = fields.Boolean(copy=False)

    guest_ids = fields.Many2many("appointment.guests")

    def _create_hikcentral_visitor_users(self):
        """
        Creates individual 'hikcentral.users' records for each guest.
        Logic:
        1. Checks for Default Visitor Department/Access Levels.
        2. If not found, inherits from the Host.
        3. Syncs to HikCentral and sends QR email.
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
                _logger.info("Event group %s skipped: no guests found.", access_token)
                continue
            
            if any(event.hikcentral_synced for event in event_group) and not self.env.context.get('from_web'):
                _logger.info("Event group %s has already been processed.", access_token)
                continue

            try:
                hik_host = self.env["hikcentral.users"].search(
                    [("partner_id", "=", primary_event.appointment_booker_id.id)],
                    limit=1,
                )

                host_department = hik_host.department_id if hik_host else False
            
                default_dept = self.env["hikcentral.department"].search(
                    [("default_visitor_department", "=", True)], limit=1
                )
                target_department_id = (
                    default_dept.id if default_dept else host_department.id
                )

                if not target_department_id:
                    primary_event.message_post(
                        body="Error: No Department found (neither Default nor Host)."
                    )
                    continue

                default_levels = self.env["hikcentral.access.level"].search(
                    [("default_visitor_access_level", "=", True)]
                )

                if default_levels:
                    target_level_ids = default_levels.ids
                else:
                    host_access_levels = hik_host.access_level_ids
                    target_level_ids = host_access_levels.ids if host_access_levels else []

                start_datetime = min(event_group.mapped("start"))
                end_datetime = max(event_group.mapped("stop"))
                start_datetime -= timedelta(minutes=30)
                end_datetime += timedelta(minutes=30)

                created_users_count = 0

                for guest in primary_event.guest_ids:
                    name_parts = (guest.name or "Invitado").split(" ", 1)
                    first_name = name_parts[0]
                    last_name = name_parts[1] if len(name_parts) > 1 else "Visitor"

                    visitor_vat = guest.vat or f"GUEST{guest.id}"

                    visitor_vals = {
                        "is_visitor": True,
                        "visitor_name": first_name,
                        "visitor_last_name": last_name,
                        "visitor_vat": visitor_vat,
                        "visitor_email": guest.email,
                        "start_date": start_datetime,
                        "end_date": end_datetime,
                        "department_id": target_department_id,
                        "access_level_ids": [(6, 0, target_level_ids)],
                        "state": "draft",
                        "event_id": primary_event.id,
                        "appointment_guest_id": guest.id,
                        "comes_from_calendar_reservation": True,
                    }

                    new_hik_user = self.env["hikcentral.users"].create(visitor_vals)

                    new_hik_user.generate_card_qr_codes()

                    if new_hik_user.state == "synced" and new_hik_user.qr_code_image:
                        new_hik_user.action_send_qr_email()
                        created_users_count += 1
                    else:
                        primary_event.message_post(
                            body=f"Failed to sync visitor: {guest.name}"
                        )

                if created_users_count > 0:
                    event_group.write({"hikcentral_synced": True})
                    primary_event.message_post(
                        body=_(
                            "HikCentral Sync: %s visitors processed"
                        )
                        % (
                            created_users_count,
                            (
                                default_dept.name
                            ),
                        )
                    )

            except Exception as e:
                error_msg = _("Failed to process visitor sync: %s") % str(e)
                primary_event.message_post(body=error_msg)
                _logger.exception("Error in _create_hikcentral_visitor_users")


    def get_guest_hik_qr(self, guest_id):
        """
        Returns the base64 URI of the QR code for a specific guest in this event.
        Used from QWeb.
        """
        self.ensure_one()
        if not guest_id:
            return False

        hik_user = self.env["hikcentral.users"].search([
            ('event_id', '=', self.id),
            ('appointment_guest_id', '=', guest_id),
            ('qr_code_image', '!=', False)
        ], limit=1)

        if hik_user:
            return image_data_uri(hik_user.qr_code_image)
        
        return False