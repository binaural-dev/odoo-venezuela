import json
import logging
from datetime import datetime
from collections import OrderedDict
import re
import pytz
from werkzeug.exceptions import Forbidden, NotFound

from odoo import _, http, fields
from odoo.http import request
from odoo.osv import expression


_logger = logging.getLogger(__name__)
FIELDSRESERVATION = ["name", "product_id"]
FIELDSRESERVATIONMADE = [
    "start",
    "start_date",
    "stop",
    "stop_date",
    "duration",
    "appointment_type_id",
    "categ_ids",
    "partner_id",
    "partner_ids",
]


class MainCalendar(http.Controller):

    @http.route(
        [
            "/reservation_calendar",
        ],
        type="http",
        auth="public",
        website=True,
    )
    def website_reservation_calendar(self, **kw):
        return request.render(
            "cadipa_reservation_calendar.cadipa_reservation_calendar",
            {},
        )

    @http.route("/get_reservations", type="json", auth="public")
    def get_reservations_info(self):
        data = {"status": 200, "msg": _("Success")}
        reservations = False
        try:
            reservations = request.env["appointment.type"].sudo().search_read(
                domain=self._domain_reservation(), fields=FIELDSRESERVATION, order="id asc"
            )
        except Exception as e:
            data.update(
                {
                    "status": 400,
                    "msg": str(e),
                }
            )
        data.update(
            {
                "reservation": reservations,
            }
        )
        return data

    @http.route("/get_reservations_made", type="json", auth="public")
    def get_reservations_made(self):
        data = {"status": 200, "msg": _("Success")}
        reservations = False
        reservation_list = []
        try:
            reservations = request.env["calendar.event"].sudo().search(
                domain=self._domain_reservation_made(), order="appointment_type_id asc"
            )
            for res in reservations:
                res_dict = self._info_partner_with_reservation(res)
                reservation_list.append(res_dict)
        except Exception as e:
            data.update(
                {
                    "status": 400,
                    "msg": str(e),
                }
            )
        data.update(
            {
                "reservation_partners": reservation_list,
            }
        )
        return data

    @http.route("/get_opening_and_closing_time", type="json", auth="public")
    def get_opening_and_closing_time(self):
        data = {"status": 200, "msg": _("Success")}
        company_id = self._get_company_from_current_website()
        opening_time = company_id.appointment_open_hour if company_id.appointment_open_hour else 0
        closing_time = (
            company_id.appointment_close_hour if company_id.appointment_close_hour else 24
        )
        data.update(
            {
                "open": opening_time,
                "close": closing_time,
            }
        )
        return data

    def _get_company_from_current_website(self):
        website_id = request.env["website"].sudo().get_current_website()
        return website_id.company_id

    def _domain_reservation(self):
        domain = [("product_id", "!=", False), ("active", "=", True), ("is_published", "=", True)]
        return domain

    def _domain_reservation_made(self):
        user = request.env.user
        user_tz = pytz.timezone(user.tz or "UTC")
        current_datetime = pytz.utc.localize(fields.Datetime.now()).astimezone(user_tz)
        init_today = current_datetime.replace(hour=0, minute=0, second=0)
        end_today = current_datetime.replace(hour=23, minute=59, second=59)

        init_today_utc = init_today.astimezone(pytz.utc)
        end_today_utc = end_today.astimezone(pytz.utc)

        domain = [
            ("appointment_type_id.product_id", "!=", False),
            ("active", "=", True),
            ("start", ">=", init_today_utc),
            ("stop", "<=", end_today_utc),
            (
                "categ_ids",
                "in",
                request.env.ref("appointment.calendar_event_type_data_online_appointment").ids,
            ),
        ]
        return domain

    def _info_partner_with_reservation(self, reservation):
        partner_id = {}
        invoice = {}
        if reservation.invoice_ids:
            invoice = {
                "id": reservation.invoice_ids[0].id,
                "name": reservation.invoice_ids[0].name,
                "state": reservation.invoice_ids[0].state,
                "payment_state": reservation.invoice_ids[0].payment_state,
            }
        if reservation.partner_ids:
            for partner in reservation.partner_ids.filtered(
                lambda p: p.id != reservation.partner_id.id
            ):
                partner_id = {"id": partner.id, "name": partner.name}
        start_time_12h = reservation.start.astimezone(pytz.timezone(request.env.user.tz)).strftime(
            "%I:%M %p"
        )
        stop_time_12h = reservation.stop.astimezone(pytz.timezone(request.env.user.tz)).strftime(
            "%I:%M %p"
        )
        question = reservation.appointment_type_id.question_ids.filtered(
            lambda q: q.show_in_calendar
        )
        
        pattern = re.compile(r'<li>(.*?)</li>', re.IGNORECASE)
        matches = pattern.findall(reservation.description)
        
        answer = ""
        if reservation.description and question:
            pattern = re.compile(r'<li>(.*?)</li>', re.IGNORECASE)
            matches = pattern.findall(reservation.description)
            
            for match in matches:
                if question.name in match:
                    answer = match.replace(f"{question.name}: ", '')
                    break

        partner = {
            "start": start_time_12h,
            "start_date": reservation.start.date(),
            "stop": stop_time_12h,
            "stop_date": reservation.stop.date(),
            "appointment_type_id": {
                "id": reservation.appointment_type_id.id,
                "name": reservation.appointment_type_id.name,
            },
            "product_id": {
                "id": reservation.appointment_type_id.product_id.id,
                "name": reservation.appointment_type_id.product_id.name,
            },
            "invoice": invoice,
            "categ_ids": {"id": reservation.categ_ids[0].id, "name": reservation.categ_ids[0].name},
            "responsible": {"id": reservation.partner_id.id, "name": reservation.partner_id.name},
            "partner_id": partner_id,
            "message": {
                "question": question.name if question else '',
                "answer": answer,
            },
        }
        return partner
