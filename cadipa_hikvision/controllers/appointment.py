import logging
from odoo import http, fields, _
from odoo.http import request
from datetime import timedelta
import json
from odoo.addons.cadipa_appointment.controllers.appointment import (
    AppointmentControllerMulti,
)

_logger = logging.getLogger(__name__)


class CadipaWebsiteAppointment(AppointmentControllerMulti):

    def _post_submission_hook(self, created_events):
        """
        Override the parent hook to trigger synchronization
        with HikCentral for newly created events.
        """
        super(CadipaWebsiteAppointment, self)._post_submission_hook(created_events)

        if created_events:
            try:
                created_events.sudo()._create_hikcentral_visitor_users()
            except Exception as e:
                _logger.error(
                    "Failed to initiate synchronization with HikCentral from the hook: %s",
                    e,
                )

    def _is_last_attendee(self, event):
        """
        Auxiliary function to check if the event has only one attendee left
        (combining guests and partners).
        """
        if not event:
            return True
        total_count = len(event.guest_ids) + len(event.partner_ids)
        _logger.info("Total attendees (guests + partners): %d", total_count)

        return total_count <= 1

    @http.route(
        ["/appointment/guest/resend_email_json"],
        type="json",
        auth="public",
        methods=["POST"],
        website=True,
    )
    def appointment_guest_resend_email_json(
        self, access_token, guest_id, email, **kwargs
    ):
        """
        JSON endpoint allowing a guest to resend their email containing the QR code.
        """

        event = (
            request.env["calendar.event"]
            .sudo()
            .search([("access_token", "=", access_token)], limit=1)
        )
        if not event:
            return {"error": _("Event not found or invalid token.")}

        guest = request.env["appointment.guests"].sudo().browse(int(guest_id))
        if not guest or guest not in event.guest_ids:
            return {"error": _("Guest not found in this event.")}

        try:
            guest.write({"email": email})

            hik_user = (
                request.env["hikcentral.users"]
                .sudo()
                .search(
                    [
                        ("appointment_guest_id", "=", guest.id),
                        ("event_id", "=", event.id),
                    ],
                    limit=1,
                )
            )

            if hik_user:
                hik_user.write({"visitor_email": email})
                hik_user.action_send_qr_email()
                return {
                    "success": True,
                    "msg": _("Email updated and QR resent successfully."),
                }
            else:
                return {"error": _("No synchronized user found in HikCentral.")}

        except Exception as e:
            return {"error": str(e)}

    @http.route(
        "/appointment/guest/delete_json", type="json", auth="public", website=True
    )
    def delete_guest_json(self, access_token, guest_id):
        """
        JSON endpoint to delete a guest from an appointment event,
        including removing their access from HikCentral.
        """
        event = (
            request.env["calendar.event"]
            .sudo()
            .search([("access_token", "=", access_token)], limit=1)
        )
        if not event:
            return {"error": _("Event not found.")}

        guest = request.env["appointment.guests"].sudo().browse(int(guest_id))
        if not guest:
            return {"error": _("Guest not found.")}

        if self._is_last_attendee(event):
            return {"error": _("You cannot delete the last guest. The booking cannot be empty.")}
        
        try:
            hik_user = (
                request.env["hikcentral.users"]
                .sudo()
                .search(
                    [
                        ("event_id", "=", event.id),
                        ("appointment_guest_id", "=", guest.id),
                    ],
                    limit=1,
                )
            )

            if hik_user:
                if hik_user.hikcentral_person_api_id:
                    try:
                        hik_user.action_delete_from_hikcentral()
                        hik_user.action_send_cancellation_email()
                    except Exception as e:
                        _logger.warning(
                            f"Failed to delete from HikCentral API; proceeding with local deletion: {e}"
                        )
                hik_user.unlink()

            event.write({"guest_ids": [(3, guest.id)]})

            return {"success": True}

        except Exception as e:
            request.env.cr.rollback()
            return {"error": str(e)}

    @http.route(
        ["/appointment/add/single_guest_ajax/<string:access_token>"],
        type="http",
        auth="public",
        methods=["POST"],
        website=True,
        csrf=True,
    )
    def appointment_add_single_guest_ajax(self, access_token, **post):
        """
        Adds the guest, checks for duplicates, and triggers immediate synchronization
        with HikCentral (creation + QR + email).
        """
        event = (
            request.env["calendar.event"]
            .sudo()
            .search([("access_token", "=", access_token)], limit=1)
        )

        guest_id = post.get("guest_id")

        if not event or not guest_id:
            return self._json_response("error", "Event or Guest not found")

        try:
            guest_id = int(guest_id)
            guest = request.env["appointment.guests"].sudo().browse(guest_id)

            if not guest:
                return self._json_response("error", "Guest Record not found")

            if guest_id in event.guest_ids.ids:
                return self._json_response("info", "The guest already exists")

            if guest.vat:
                if self._check_double_booking(event, guest):
                    error_msg = _(
                        "The guest %s (%s - %s) already has another booking on this day."
                    ) % (
                        guest.name,
                        guest.prefix_vat,
                        guest.vat,
                    )
                    request.session["delete_error"] = error_msg
                    return self._json_response("reload_required", error_msg)

            event.sudo().write({"guest_ids": [fields.Command.link(guest_id)]})

            try:
                _logger.info(
                    f"Syncing guest {guest.name} to HikCentral for event {event.id}..."
                )
                event.with_context(from_web=True)._create_hikcentral_visitor_users()

                return self._json_response("ok", "Guest added and Synced to HikCentral")

            except Exception as e_hik:
                _logger.exception("HikCentral Sync Failed during Add Guest: %s", e_hik)
                return self._json_response(
                    "info",
                    _("Guest added locally, but HikCentral sync failed: %s")
                    % str(e_hik),
                )
        except Exception as e:
            _logger.exception("Error adding guest")
            return self._json_response("error", str(e))

    def _check_double_booking(self, event, guest):
        """Check if the guest has another booking on the same day."""
        event_start_dt = fields.Datetime.from_string(event.start)
        day_start_utc = event_start_dt.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_end_utc = day_start_utc + timedelta(days=1, microseconds=-1)

        domain = [
            ("guest_ids.vat", "=", guest.vat),
            ("start", ">=", fields.Datetime.to_string(day_start_utc)),
            ("start", "<=", fields.Datetime.to_string(day_end_utc)),
            ("id", "!=", event.id),
        ]
        return request.env["calendar.event"].sudo().search_count(domain) > 0

    def _json_response(self, status, message):
        """Helper to return a standardized JSON response."""
        return request.make_response(
            json.dumps({"status": status, "message": message}),
            headers=[("Content-Type", "application/json")],
        )
