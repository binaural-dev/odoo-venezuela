from odoo.addons.binaural_appointment.controllers.appointment import (
    AppointmentController
)
from werkzeug.urls import url_parse, url_encode, url_unparse
from odoo.exceptions import ValidationError

from urllib.parse import parse_qs, unquote_plus
from odoo.http import route, request
from odoo import fields
from dateutil.relativedelta import relativedelta
import json, pytz, logging
from babel.dates import format_datetime
from odoo import Command, exceptions, http, fields, _
from datetime import datetime, time

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

        validation_error = kwargs.get('validation_error') 
        guest_creation_error = kwargs.get('error')

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
        
        clean_kwargs.pop('validation_error', None) 
        clean_kwargs.pop('error', None) 

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
        
        if validation_error:
            resp.qcontext['validation_error'] = validation_error
            
        if guest_creation_error:                     
            if guest_creation_error == 'guest_creation_failed':
                 resp.qcontext['guest_creation_error'] = "Error al crear el invitado. Intente de nuevo."
            else:
                 resp.qcontext['guest_creation_error'] = guest_creation_error
            
        return resp
    
    @route(['/appointment/<int:appointment_type_id>/submit'],
       auth='public', website=True, type='http', methods=['POST'], priority=400)
    def appointment_form_submit(self, appointment_type_id, multi_slots=None, **post):
        try:
            guest_ids_str = post.get("guest_ids", "") 
            guest_ids = [int(gid) for gid in guest_ids_str.split(',') if gid.isdigit()]
            
            if guest_ids:
                incoming_guests = request.env['appointment.guests'].sudo().browse(guest_ids)
                incoming_vats = [v for v in incoming_guests.mapped('vat') if v]

                if incoming_vats:
                    date_str = None
                    if multi_slots:
                        slots_data = json.loads(multi_slots)
                        if slots_data:
                            first_dt, _duration, _params = _parse_slot(slots_data[0])
                            date_str = fields.Datetime.to_string(first_dt)
                    else:
                        date_str = post.get('date_time')

                    if date_str:
                        appointment_dt_utc = fields.Datetime.from_string(date_str)
                        appointment_date = appointment_dt_utc.date()
                        
                        day_start_utc = datetime.combine(appointment_date, time.min)
                        day_end_utc = datetime.combine(appointment_date, time.max)
                        

                        domain = [
                            ('guest_ids.vat', 'in', incoming_vats),
                            ('start', '>=', day_start_utc),
                            ('start', '<=', day_end_utc),
                        ]
                        
                        existing_events = request.env['calendar.event'].sudo().search(domain)
                        
                        if existing_events:                            
                            attendees_in_conflict = existing_events.mapped('guest_ids')
                            vats_in_conflict = set(attendees_in_conflict.mapped('vat'))
                            
                            conflicting_incoming_vats = set(incoming_vats) & vats_in_conflict
                            
                            conflicting_guests = incoming_guests.filtered(
                                lambda p: p.vat in conflicting_incoming_vats
                            )
                            guest_names = ", ".join(conflicting_guests.mapped('name'))
                            
                            error_msg = "Uno o más invitados (%s) ya tienen una reserva para este día." % guest_names
                            raise ValidationError(error_msg)

        except ValidationError as e:
            _logger.error("Error de validación de invitado (Conflicto de Horario por VAT): %s", str(e))
            query_params = post.copy() 
            query_params['multi_slots'] = multi_slots
            query_params['validation_error'] = str(e)
            info_url = f"/appointment/{appointment_type_id}/info"
            return request.redirect(info_url + '?' + url_encode(query_params))
        
        
        if not multi_slots:
            try:
                guest_ids = self._extract_ids(post, "guest_ids")
                beneficiary_ids = self._extract_ids(post, "family_guest_ids")
                total_guests = len(guest_ids) + len(beneficiary_ids) + (1 if post.get('attend_reservation') else 0)
                resource_capacity = post.get('resource_capacity')

                if total_guests > resource_capacity:
                    raise ValidationError(_("The number of guests exceeds the resource capacity."))

                response = super(AppointmentControllerMulti, self).appointment_form_submit(
                    appointment_type_id, multi_slots=multi_slots, **post
                )
                if response.status_code == 303 and 'calendar/view' in response.location:
                    access_token = response.location.split('/calendar/view/')[1].split('?')[0]
                    created_event = request.env['calendar.event'].sudo().search([('access_token', '=', access_token)], limit=1)
                    
                    guest_ids = self._extract_ids(post, "guest_ids")
                    beneficiary_ids = self._extract_ids(post, "family_guest_ids")
                       
                    update_vals = {}

                    if guest_ids:
                        update_vals['guest_ids'] = [Command.set(guest_ids)]
                    if beneficiary_ids:
                        current_partners_ids = created_event.partner_ids.ids
                        all_partners_ids = list(set(current_partners_ids + beneficiary_ids))
                        update_vals['partner_ids'] = [Command.set(all_partners_ids)]

                    if created_event and update_vals:
                        created_event.sudo().write(update_vals)
                        created_event = created_event.exists()
                    
                    self._post_submission_hook(created_event)
                
                return response
            
            except ValidationError as e:
                _logger.error("Error de validación de invitado: %s", str(e))
                query_params = post.copy()
                query_params['validation_error'] = str(e)
                info_url = f"/appointment/{appointment_type_id}/info"
                return request.redirect(info_url + '?' + url_encode(query_params))
        
        try:
            guest_ids = self._extract_ids(post, "guest_ids")
            beneficiary_ids = self._extract_ids(post, "family_guest_ids")
            attend_reservation = post.get('attend_reservation')
            total_guests = len(guest_ids) + len(beneficiary_ids) + (1 if attend_reservation else 0)
            resource_capacity = int(post.get('resource_capacity', 0))

            if total_guests > resource_capacity:
                raise ValidationError(_("The number of guests exceeds the resource capacity."))

            if total_guests <= 0:
                raise ValidationError(_("You must select at least one guest or attend yourself."))

            slots = sorted((_parse_slot(q) for q in json.loads(multi_slots)),
                        key=lambda s: s[0])
            
            time_ranges = []
            current_start, current_duration = slots[0][0], slots[0][1]
            current_end = current_start + relativedelta(hours=current_duration)
            total_hours = current_duration
            for slot_start, slot_duration, __ in slots[1:]:
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
            
            customer = request.env['res.partner'].sudo().browse(int(customer_id)) if customer_id else None
            if not customer:
                customer = request.env.user.partner_id
            
            if customer:
                if not customer.vat:
                    customer.write({'vat':vat})
                if not customer.phone:
                    customer.write({'phone':phone})
            
            appointment_type = request.env['appointment.type'].sudo().browse(appointment_type_id)

            first_slot_start = ranges[0][0]
            
            staff_user = None
            first_slot_params = slots[0][2]
            resource_id = None
            
            if appointment_type.schedule_based_on == 'users':
                staff_user_id = first_slot_params.get('staff_user_id')
                if staff_user_id:
                    staff_user = request.env['res.users'].sudo().browse(int(staff_user_id))

            if appointment_type.schedule_based_on == 'resources':
                resource_ids_str = first_slot_params.get('available_resource_ids')

                if resource_ids_str:
                    try:
                        resource_id_list = json.loads(resource_ids_str)
                        if resource_id_list:
                            first_resource_id = resource_id_list[0] 
                            resource = request.env['appointment.resource'].sudo().browse(first_resource_id)
                            resource_id = resource.id if resource else None            
                    except json.JSONDecodeError:
                        _logger.error("Error decoding JSON for available_resource_ids: %s", resource_ids_str)
                        return

            self._check_appointment_frequency_limit(customer, appointment_type, first_slot_start, resource_id=resource_id)
            
            product_id = post.get('product_id')
            created_ev = request.env['calendar.event']
            first_token = None
            booking_vals = []

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
                    create_invoice     = False,
                    resource_id        = resource_id,
                )

                if ev:
                    if not first_token:
                        first_token = ev.access_token
                    else:
                        ev.write({'access_token': first_token})
                    created_ev |= ev


            update_vals = {}
            if guest_ids:
                update_vals['guest_ids'] = [Command.set(guest_ids)]
            if beneficiary_ids:
                booking_partner_id = customer.id
                final_partners_ids = []
                
                final_partners_ids.extend(beneficiary_ids)
                
                if attend_reservation:
                    final_partners_ids.append(booking_partner_id)

                unique_partners_ids = list(set(final_partners_ids))
                update_vals['partner_ids'] = [Command.set(unique_partners_ids)]
            
            if created_ev and update_vals:
                created_ev.sudo().write(update_vals)
                created_ev = created_ev.exists()

            has_membership_active = customer.action_number.state == 'active' if customer.action_number else False

            if created_ev and product_id and not has_membership_active:
                created_ev.sudo().create_invoices({
                    'product_id': product_id,
                    'duration'  : total_hours,
                    'partner_id': customer.id,
                })
                if not created_ev.invoice_ids.partner_id:
                    created_ev.invoice_ids.sudo().write({'partner_id': customer.id})
            
            self._post_submission_hook(created_ev)

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

        except ValidationError as e:
            _logger.error("Error de validación de invitado (multi-slot): %s", str(e))
            query_params = post.copy() 
            query_params['multi_slots'] = multi_slots
            query_params['validation_error'] = str(e)
            info_url = f"/appointment/{appointment_type_id}/info"
            return request.redirect(info_url + '?' + url_encode(query_params))

    def _post_submission_hook(self, created_events):
        """
        Empty hook to be extended by other modules (e.g., cadipa_hikvision).
        Called after events have been created and before redirecting.
        :param created_events: a recordset of 'calendar.event' with the created events.
        """
        pass
    
    @staticmethod
    def _extract_ids(post, key):
        ids_str = post.get(key, "") 
        return [int(gid) for gid in ids_str.split(',') if gid.isdigit()]

    def _handle_appointment_form_submission(
        self, appointment_type,
        date_start, date_end, duration,
        description, answer_input_values, name, customer, appointment_invite,
        product_id, guests=None,
        staff_user=None, resource_id=None, asked_capacity=1, booking_line_values=None,
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
                date_start, date_end,
                resource_id=resource_id
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
    
    def _check_appointment_frequency_limit(self, customer, appointment_type, target_datetime, resource_id=None):
        """
        Valida frecuencia basada en configuración de EMPRESA, pero aplicada por TIPO o RECURSO.
        """
        company = request.env.company

        tz_name = request.session.get('timezone') or appointment_type.appointment_tz or request.env.user.tz or 'UTC'
        tz = pytz.timezone(tz_name)

        target_utc = tz.localize(target_datetime).astimezone(pytz.utc).replace(tzinfo=None)

        local_date = target_datetime.date()
        local_start = tz.localize(datetime.combine(local_date, time.min))
        local_end = tz.localize(datetime.combine(local_date, time.max))

        start_of_day_utc = local_start.astimezone(pytz.utc).replace(tzinfo=None)
        end_of_day_utc = local_end.astimezone(pytz.utc).replace(tzinfo=None)

        restrict_appointment_to_members = company.restrict_appointment_to_members
        restricted_days = company.appointment_lead_time_days

        if restrict_appointment_to_members and restricted_days and restricted_days > 0:
            start_bound = target_utc - relativedelta(days=restricted_days)
            end_bound = target_utc + relativedelta(days=restricted_days)

            domain = [
                ('partner_ids', 'in', [customer.id]),
                ('appointment_booker_id', '=', customer.id),
                ('appointment_type_id', '=', appointment_type.id),
                ('start', '>=', start_bound),
                ('start', '<=', end_bound),
            ]

            existing_count = request.env['calendar.event'].sudo().search_count(domain)

            if existing_count > 0:
                raise ValidationError(
                    _("Due to company policy, you cannot schedule another appointment of this type (%s) within a %s-day period.")
                    % (appointment_type.name, restricted_days)
                )

        if resource_id:
            resource = request.env['appointment.resource'].sudo().browse(resource_id)
            same_day_domain = [
                ('partner_ids', 'in', [customer.id]),
                ('appointment_booker_id', '=', customer.id),
                ('start', '>=', start_of_day_utc),
                ('start', '<=', end_of_day_utc),
                ('appointment_resource_ids', 'in', [resource_id]),
            ]
            existing_same_day = request.env['calendar.event'].sudo().search_count(same_day_domain)
            if existing_same_day > 0:
                raise ValidationError(
                    _("Due to company policy, it is not possible to reserve the same type of space (%s) more than once a day.")
                    % (resource.name)
                )
