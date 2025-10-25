import json
import pytz
import logging
from dateutil.relativedelta import relativedelta
from babel.dates import format_datetime
from werkzeug.urls import url_unparse, url_encode

from odoo.http import request, route
from odoo.addons.cadipa_appointment.controllers.appointment import (
    AppointmentControllerMulti,
    _parse_slot,
)

_logger = logging.getLogger(__name__)


class CadipaWebsiteAppointment(AppointmentControllerMulti):

    @route(
        ["/appointment/<int:appointment_type_id>/submit"],
        auth="public",
        website=True,
        type="http",
        methods=["POST"],
        priority=1000,
    )
    def appointment_form_submit(self, appointment_type_id, multi_slots=None, **post):
        # ── 1. Lógica de multi-slots (copiada de cadipa_appointment) ──
        if not multi_slots:
            # Si no es multi-slot, podemos usar el super() de la clase padre (cadipa_appointment)
            # que a su vez llamará a la lógica de un solo slot.
            response = super(CadipaWebsiteAppointment, self).appointment_form_submit(
                appointment_type_id, **post
            )
            if response.status_code == 303 and "calendar/view" in response.location:
                self._trigger_hikcentral_sync_from_response(response)
            return response

        _logger.info(
            "Procesando cita multi-slot en el controlador  de cadipa_hikvision."
        )

        # Copiamos toda la lógica de 'cadipa_appointment' aquí
        slots = sorted(
            (_parse_slot(q) for q in json.loads(multi_slots)), key=lambda s: s[0]
        )
        time_ranges = []
        current_start, current_duration = slots[0][0], slots[0][1]
        current_end = current_start + relativedelta(hours=current_duration)
        total_hours = current_duration
        for slot_start, slot_duration, _ in slots[1:]:
            slot_end = slot_start + relativedelta(hours=slot_duration)
            total_hours += slot_duration
            if slot_start == current_end:
                current_end = slot_end
            else:
                time_ranges.append((current_start, current_end))
                current_start, current_end = slot_start, slot_end
        time_ranges.append((current_start, current_end))
        ranges = time_ranges

        tz_name = request.session.get("timezone", post.get("appointment_tz", "UTC"))
        tz = pytz.timezone(tz_name)
        location = request.env.context.get("lang", "es_ES")

        date_str = format_datetime(
            ranges[0][0], "EEE d MMM y", locale=location, tzinfo=tz
        )
        hours_str = ", ".join(
            f"{s.strftime('%H:%M')} – {e.strftime('%H:%M')}" for s, e in ranges
        )
        time_locale_str = f"{date_str} {hours_str}"

        customer_id = post.get("customer_id")
        vat = post.get("vat")
        phone = post.get("phone")

        customer = (
            request.env["res.partner"].sudo().browse(int(customer_id))
            if customer_id
            else None
        )
        if not customer:
            customer = request.env.user.partner_id

        if customer:
            if not customer.vat:
                customer.write({"vat": vat})
            if not customer.phone:
                customer.write({"phone": phone})
        
        appointment_type = (
            request.env["appointment.type"].sudo().browse(appointment_type_id)
        )

        # 2. Determinar el Staff User (a quien se reserva)
        staff_user = None
        first_slot_params = slots[0][2] # Parámetros del primer slot

        if appointment_type.schedule_based_on == 'users':
            staff_user_id = first_slot_params.get('staff_user_id')
            if staff_user_id:
                staff_user = request.env['res.users'].sudo().browse(int(staff_user_id))
        else:
            # Lógica para 'resources' (si es necesaria)
            pass
        
        # --- FIN DEL BLOQUE CORREGIDO ---

        product_id = post.get("product_id")
        created_ev = request.env["calendar.event"]
        first_token = None
        booking_vals = []

        # ── 2. Creación de eventos (llamando al método correcto) ──
        for st_local, en_local in ranges:
            st_utc = tz.localize(st_local).astimezone(pytz.utc).replace(tzinfo=None)
            en_utc = tz.localize(en_local).astimezone(pytz.utc).replace(tzinfo=None)
            single_dur = (en_local - st_local).total_seconds() / 3600.0

            # ESTA ES LA LLAMADA CLAVE: usamos el método de la clase padre que sí funciona
            ev = super(
                CadipaWebsiteAppointment, self
            )._handle_appointment_form_submission(
                appointment_type=appointment_type,
                date_start=st_utc,
                date_end=en_utc,
                duration=single_dur,
                description="",
                answer_input_values=[],
                name=post.get("name"),
                customer=customer,         # Partner del Cliente
                appointment_invite=None,
                product_id=product_id,
                guests=None,
                staff_user=staff_user,     # Empleado/Doctor (corregido)
                asked_capacity=int(post.get("asked_capacity", 1)),
                booking_line_values=booking_vals,
                create_invoice=False,
            )

            guest_ids_str = post.get("guest_ids", "")
            guest_ids_int = [int(gid) for gid in guest_ids_str.split(',') if gid.isdigit()]

            if guest_ids_int:
                ev.write({"guest_ids": [(6, 0, guest_ids_int)]})

            
            if ev:
                if not first_token:
                    first_token = ev.access_token
                else:
                    ev.write({"access_token": first_token})
                created_ev |= ev

        has_membership_active = (
            customer.action_number.state == "active"
            if customer.action_number
            else False
        )

        if created_ev and product_id and not has_membership_active:
            created_ev.sudo().create_invoices(
                {
                    "product_id": product_id,
                    "duration": total_hours,
                    "partner_id": customer.id,
                }
            )
            if not created_ev.invoice_ids.partner_id:
                created_ev.invoice_ids.sudo().write({"partner_id": customer.id})

        # ── 3. Sincronización con HikCentral ──
        if created_ev:
            try:
                created_ev._create_hikcentral_visitor_appointment()
            except Exception as e:
                _logger.error(
                    "No se pudo iniciar la sincronización con HikCentral desde el controlador: %s",
                    e,
                )

        # ── 4. Redirección final ──
        if first_token:
            query = {
                "partner_id": customer.id,
                "state": "new",
                "duration_str": total_hours,
                "time_locale": time_locale_str,
            }
            return request.redirect(
                url_unparse(
                    ("", "", f"/calendar/view/{first_token}", url_encode(query), "")
                )
            )

        return request.redirect("/appointment/booking_error")

    def _trigger_hikcentral_sync_from_response(self, response):
        """Helper para no repetir código."""
        try:
            access_token = response.location.split("/calendar/view/")[1].split("?")[0]
            created_event = (
                request.env["calendar.event"]
                .sudo()
                .search([("access_token", "=", access_token)], limit=1)
            )
            if created_event:
                created_event._create_hikcentral_visitor_appointment()
        except Exception as e:
            _logger.error(
                "Fallo al disparar la sincronización de HikCentral desde la respuesta: %s",
                e,
            )
