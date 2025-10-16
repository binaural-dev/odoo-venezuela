from urllib import response
from odoo.addons.binaural_appointment.controllers.appointment import (
    AppointmentController
)
from werkzeug.urls import url_parse, url_encode, url_unparse

from urllib.parse import parse_qs, unquote_plus
from odoo.http import route, request
from odoo import fields
from dateutil.relativedelta import relativedelta
import json, pytz, logging
from babel.dates import format_datetime
from odoo import Command, exceptions, http, fields, _

_logger = logging.getLogger(__name__)


def _parse_slot(raw_qs):
    """
    "date_time=2025-06-30+10:00:00&duration=1.5&staff_user_id=6"
        → (dt_utc, dur_h, params_dict)
    """
    params = {k: v[0] for k, v in parse_qs(raw_qs).items()}
    date_str = unquote_plus(params['date_time']).replace('+', ' ')
    return (
        fields.Datetime.from_string(date_str), 
        float(params['duration']), 
        params
    )


class AppointmentControllerMulti(AppointmentController):

    @route(
        ['/appointment/<int:appointment_type_id>/info'],
        auth='public', type='http', website=True, sitemap=False, priority=400
    )
    def appointment_type_id_form(
        self, appointment_type_id,
        date_time=None, duration=None,
        staff_user_id=None, resource_selected_id=None,
        available_resource_ids=None, asked_capacity=1,
        **kwargs):

        multi_raw = kwargs.get('multi_slots')
        multi_list = json.loads(multi_raw) if multi_raw else []

        if multi_list:
            first_dt, first_dur, first_params = _parse_slot(multi_list[0])

            date_time = date_time or fields.Datetime.to_string(first_dt)
            duration = duration or str(first_dur)
            staff_user_id = staff_user_id or first_params.get('staff_user_id')
            resource_selected_id = resource_selected_id or first_params.get('resource_selected_id')
            available_resource_ids = available_resource_ids or first_params.get('available_resource_ids')
            asked_capacity = asked_capacity or first_params.get('asked_capacity', 1)

        clean_kwargs = kwargs.copy()
        for dup in ('staff_user_id', 'resource_selected_id', 'available_resource_ids', 'asked_capacity'):
            clean_kwargs.pop(dup, None)

        resp = super().appointment_type_id_form(
            appointment_type_id,
            date_time,
            duration,
            staff_user_id,
            resource_selected_id,
            available_resource_ids,
            asked_capacity,
            **clean_kwargs
        )

        if multi_list:
            slots = sorted((_parse_slot(q) for q in multi_list), key=lambda slot: slot[0])

            time_ranges = []
            range_start, current_dur = slots[0][0], slots[0][1]
            range_end = range_start + relativedelta(hours=current_dur)
            total_hours = current_dur

            for slot_start, slot_duration, _ in slots[1:]:
                next_end = slot_start + relativedelta(hours=slot_duration)
                total_hours += slot_duration
                if slot_start == range_end:
                    range_end = next_end
                else:
                    time_ranges.append((range_start, range_end))
                    range_start, range_end = slot_start, next_end
            time_ranges.append((range_start, range_end))

            resp.qcontext.update({
                'time_locale': ", ".join(f"{start.strftime('%H:%M')} – {end.strftime('%H:%M')}" for start, end in time_ranges),
                'multi_slots_json': multi_raw,
                'datetime_str': fields.Datetime.to_string(time_ranges[0][0]),
                'duration_str': f"{total_hours:g} h",
                'duration': total_hours,
            })
            resp.qcontext['appointment_type'] = resp.qcontext['appointment_type'].sudo().with_context(
                website_appointment_category_override='custom'
            )
        
        return resp

    
    @route(['/appointment/<int:appointment_type_id>/submit'],
       auth='public', website=True, type='http', methods=['POST'], priority=400)
    def appointment_form_submit(self, appointment_type_id, multi_slots=None, **post):
        
        # ── normal flow without multi-slots ─────────────────────────
        if not multi_slots:
            if response.status_code == 303 and 'calendar/view' in response.location:
                access_token = response.location.split('/calendar/view/')[1].split('?')[0]
                created_event = request.env['calendar.event'].sudo().search([('access_token', '=', access_token)], limit=1)
                guest_ids_str = request.httprequest.form.getlist('selected_guest_ids')
                guest_ids = [int(gid) for gid in guest_ids_str if gid.isdigit()]
                if created_event and guest_ids:
                    created_event.sudo().write({'guest_ids': [Command.set(guest_ids)]})
            return response
        
        guest_ids_str = request.httprequest.form.getlist('selected_guest_ids')
        guest_ids = [int(gid) for gid in guest_ids_str if gid.isdigit()]

        # ── parsing and group ───────────────────────────────
        slots = sorted((_parse_slot(q) for q in json.loads(multi_slots)),
                    key=lambda s: s[0])

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

        tz_name = request.session.get('timezone', post.get('appointment_tz', 'UTC'))
        tz      = pytz.timezone(tz_name)
        location     = request.env.context.get('lang', 'es_ES')

        date_str  = format_datetime(ranges[0][0], "EEE d MMM y", locale=location, tzinfo=tz)
        hours_str = ", ".join(f"{s.strftime('%H:%M')} – {e.strftime('%H:%M')}" for s, e in ranges)
        time_locale_str = f"{date_str} {hours_str}"

        customer_id = post.get('customer_id')
        vat = post.get('vat')
        phone = post.get('phone')


        customer   = request.env['res.partner'].sudo().browse(int(customer_id)) if customer_id else None
        staff_user       = request.env.user

        if not customer:
            customer= staff_user.partner_id
        if not customer.vat:
            customer.write({'vat':vat})
        if not customer.phone:
            customer.write({'phone':phone})
            
        product_id = post.get('product_id')
        created_ev = request.env['calendar.event']
        first_token = None
        appointment_type = request.env['appointment.type'].sudo().browse(appointment_type_id)
       
        booking_vals     = []

        for st_local, en_local in ranges:
            st_utc = tz.localize(st_local).astimezone(pytz.utc).replace(tzinfo=None)
            en_utc = tz.localize(en_local).astimezone(pytz.utc).replace(tzinfo=None)
            single_dur = (en_local - st_local).total_seconds() / 3600.0

            ev = self._handle_appointment_form_submission(
                appointment_type   = appointment_type,
                date_start         = st_utc,
                date_end           = en_utc,
                duration           = single_dur,
                description        = '',
                answer_input_values= [],
                name               = post.get('name'),
                customer           = customer,
                appointment_invite = None,
                product_id         = product_id,
                guests             = None,
                staff_user         = staff_user,
                asked_capacity     = int(post.get('asked_capacity', 1)),
                booking_line_values= booking_vals,
                create_invoice     = False
            )

            if ev:
                if not first_token:
                    first_token = ev.access_token
                else:
                    ev.write({'access_token': first_token})
                created_ev |= ev

            if created_ev and guest_ids:
                created_ev.sudo().write({'guest_ids': [Command.set(guest_ids)]})

        
        has_membership_active = customer.action_number.state == 'active' if customer.action_number else False

        # ── single invoice with multiple lines ─────────────────────────
        if created_ev and product_id and not has_membership_active:
            created_ev.sudo().create_invoices({
                'product_id': product_id,
                'duration'  : total_hours,
                'partner_id': customer.id,
            })
            if not created_ev.invoice_ids.partner_id:
                created_ev.invoice_ids.sudo().write({'partner_id': customer.id})

        if first_token:
            query = {
                'partner_id'  : customer.id,
                'state'       : 'new',
                'duration_str': total_hours,
                'time_locale' : time_locale_str,
            }
            return request.redirect(
                url_unparse(('', '', f'/calendar/view/{first_token}', url_encode(query), ''))
            )

        return request.redirect('/appointment/booking_error')

    def _handle_appointment_form_submission(
        self, appointment_type,
        date_start, date_end, duration,
        description, answer_input_values, name, customer, appointment_invite,
        product_id, guests=None,
        staff_user=None, asked_capacity=1, booking_line_values=None,
        create_invoice=False):

        staff_user = staff_user and staff_user.exists() or None
        organizer  = staff_user or appointment_type.create_uid
        event = request.env['calendar.event'].with_context(
            mail_notify_author  = True,
            mail_create_nolog   = True,
            mail_create_nosubscribe = True,
            allowed_company_ids = self._get_allowed_companies(organizer).ids,
        ).sudo().create({
            'appointment_answer_input_ids': [
                Command.create(vals) for vals in answer_input_values
            ],
            **appointment_type._prepare_calendar_event_values(
                asked_capacity, booking_line_values, description, duration,
                appointment_invite or request.env['appointment.invite'],
                guests, name, customer, staff_user,
                date_start, date_end
            )
        })

        event.attendee_ids.write({'state': 'accepted'})
        has_membership_active = customer.action_number.state == 'active' if customer.action_number else False
        # invoice only if explicitly requested
        if create_invoice and product_id and not has_membership_active:
            event.sudo().create_invoices({
                'product_id': product_id,
                'duration'  : duration,
                'partner_id': customer.id,

            })
        customer.appointments_count += 1
        return event
    
    