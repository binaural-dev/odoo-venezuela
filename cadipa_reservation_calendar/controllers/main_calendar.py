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

import logging
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
    "/reservation_calendar",
    type="http",
    auth="public",
    website=True,
    )
    def website_reservation_calendar(self, **kw):
        reservation_zones = request.env["appointment.type"].sudo().search([("active", "=", True)])
        return request.render(
            "cadipa_reservation_calendar.cadipa_reservation_calendar",
            {
                'reservation_zones': reservation_zones
            }
        )


    @http.route('/get_reservations', type='json', auth='public', website=True)
    def get_reservations_info(self, court_ids=None, date=None, **kw): # 'date' se recibe pero NO se usa para filtrar las zonas aquí
        """
        court_ids arrives as a list of strings or None.
        This function returns the selected zones, regardless of their reservations for the date.
        """
        try:
            ids = [int(x) for x in court_ids] if court_ids else None
            final_appointment_type_domain = self._domain_appointment_type_base(ids)

            reservations = request.env['appointment.type'].sudo().search_read(
                domain=final_appointment_type_domain,
                fields=FIELDSRESERVATION,
                order='id asc'
            )
            return {'status': 200, 'reservation': reservations}
        except Exception as e:
            return {'status': 400, 'msg': str(e), 'reservation': []}

    def _domain_appointment_type_base(self, ids=None):
        domain = [
            ('product_id', '!=', False),
            ('active', '=', True),
        ]
        if ids:
            domain.append(('id', 'in', ids))
        return domain



    @http.route("/get_reservations_made", type="json", auth="public", website=True)
    def get_reservations_made(self, date=None, **kw):
        data = {"status": 200, "msg": _("Success")}
        reservation_list = []
        try:
            domain_for_events = self._domain_reservation_made(date=date)

            reservations = request.env["calendar.event"].sudo().search(
                domain=domain_for_events,
                order="appointment_type_id asc"
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

    def _domain_reservation_made(self, date=None): # 'date' se usa para filtrar los eventos por día
        search_date = None
        if date:
            try:
                search_date = datetime.strptime(date, '%Y-%m-%d').date()
            except ValueError:
                search_date = datetime.now().date()
        else:
            search_date = datetime.now().date()


        user = request.env.user
        user_tz = pytz.timezone(user.tz or "UTC")

        init_of_day_local = user_tz.localize(datetime(search_date.year, search_date.month, search_date.day, 0, 0, 0))
        end_of_day_local = user_tz.localize(datetime(search_date.year, search_date.month, search_date.day, 23, 59, 59))

        init_of_day_utc = init_of_day_local.astimezone(pytz.utc).replace(tzinfo=None)
        end_of_day_utc = end_of_day_local.astimezone(pytz.utc).replace(tzinfo=None)

        domain = [
            ("appointment_type_id.product_id", "!=", False),
            ("active", "=", True),
            ("start", ">=", init_of_day_utc),
            ("stop", "<=", end_of_day_utc),
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
        if not reservation:
            return False
        
        if reservation.invoice_ids:
            invoice = {
                "id": reservation.invoice_ids[0].id,
                "name": reservation.invoice_ids[0].name,
                "state": reservation.invoice_ids[0].state,
                "payment_state": reservation.invoice_ids[0].payment_state,
            }
        partner_id = {"id": reservation.partner_id.id, "name": reservation.partner_id.name}
        # se comenta en caso de que en un futuro se quiera evitar mostrar el partner principal como originalmente hacia
        # ya que el flujo de reservas ha cambiado con el tiempo y el partner principal que se llena al parecer es el que quiere reservar
        # if reservation.partner_ids:
        #     for partner in reservation.partner_ids.filtered(
        #         lambda p: p.id != reservation.partner_id.id
        #     ):
        #         partner_id = {"id": partner.id, "name": partner.name}
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
        matches = pattern.findall(reservation.description or '')
        description_output = "\n".join(matches)

        answer = ""
        if reservation.description and question:
            for match in matches: # Use the already found matches
                if question.name in match:
                    answer = match.replace(f"{question.name}: ", '')
                    break
        partner = {
            "start": start_time_12h,
            "start_date": reservation.start.date().isoformat(),
            "stop": stop_time_12h,
            "stop_date": reservation.stop.date().isoformat(),
            "description": description_output,
            "appointment_type_id": {
                "id": reservation.appointment_type_id.id,
                "name": reservation.appointment_type_id.name,
            },
            "product_id": {
                "id": reservation.appointment_type_id.product_id.id,
                "name": reservation.appointment_type_id.product_id.name,
            },
            "invoice": invoice,
            "categ_ids": {"id": reservation.categ_ids[0].id, "name": reservation.categ_ids[0].name} if reservation.categ_ids else {},
            "responsible": {"id": reservation.partner_id.id, "name": reservation.partner_id.name},
            "partner_id": partner_id,
            "message": {
                "question": question.name if question else '',
                "answer": answer,
            },
        }
        return partner
