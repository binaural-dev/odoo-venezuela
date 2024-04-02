
import json
import logging
import re
import uuid
from datetime import date, datetime

import pytz
from babel.dates import format_date, format_datetime, format_time
from dateutil.relativedelta import relativedelta
from odoo import _, exceptions, fields, http
from odoo.addons.appointment.controllers.appointment import AppointmentController
from odoo.addons.base.models.ir_qweb import keep_query
from odoo.http import request, route
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT as dtf
from odoo.tools import plaintext2html
from odoo.tools.misc import babel_locale_parse, get_lang
from werkzeug.exceptions import Forbidden, NotFound

from ..utils import has_logged

_logger = logging.getLogger(__name__)



class AppointmentController(AppointmentController):

    @http.route(['/appointment/get_data_customer'], type='json', auth="public", website=True)
    def get_data_customer(self, **kwargs):
        customer_id = kwargs.get('customer_id')
        if not customer_id:
            return {}

        customer = request.env['res.partner'].sudo().browse(int(customer_id))
        if customer:
            return {
                'name': customer.name,
                'vat': customer.vat,
                'prefix_vat': customer.prefix_vat,
                'phone': customer.phone,
                'email': customer.email
            }
        return {}

    @http.route(['/appointment/<int:appointment_type_id>/info'],
                type='http', auth="public", website=True, sitemap=False)
    def appointment_type_id_form(self, appointment_type_id, staff_user_id, date_time, duration, **kwargs):
        """
        Render the form to get information about the user for the appointment

        :param appointment_type_id: the appointment type id related
        :param staff_user_id: the user selected for the appointment
        :param date_time: the slot datetime selected for the appointment
        :param duration: the duration of the slot
        :param filter_appointment_type_ids: see ``Appointment.appointments()`` route
        """
        appointment_type = self._fetch_and_check_private_appointment_types(
            kwargs.get('filter_appointment_type_ids'),
            kwargs.get('filter_staff_user_ids'),
            kwargs.get('invite_token'),
            current_appointment_type_id=int(appointment_type_id),
        )
        if not appointment_type:
            raise NotFound()

        if not self._check_appointment_is_valid_slot(appointment_type, staff_user_id, date_time, duration, **kwargs):
            raise NotFound()

        get_prefix = request.env['res.partner']._fields['prefix_vat'].selection
        
        is_internal_user = request.env.user.has_group('base.group_user')

        if is_internal_user:
            customer_id = request.env['res.partner'].sudo().search([])

        else:
            customer_id = []


        partner = self._get_customer_partner()
        partner_data = partner.read(fields=['name', 'phone', 'email', 'prefix_vat', 'vat'])[0] if partner else {}
        date_time_object = datetime.strptime(date_time, dtf)
        day_name = format_datetime(date_time_object, 'EEE', locale=get_lang(request.env).code)
        date_formated = format_date(date_time_object.date(), locale=get_lang(request.env).code)
        time_locale = format_time(date_time_object.time(), locale=get_lang(request.env).code, format='short')
        return request.render("appointment.appointment_form", {
            'partner_data': partner_data,
            'is_internal_user': is_internal_user,
            'customer_id': customer_id,
            'prefix_vat': get_prefix,
            'appointment_type': appointment_type,
            'available_appointments': self._fetch_available_appointments(
                kwargs.get('filter_appointment_type_ids'),
                kwargs.get('filter_staff_user_ids'),
                kwargs.get('invite_token'),
            ),
            'main_object': appointment_type,
            'datetime': date_time,
            'date_locale': day_name + ' ' + date_formated,
            'time_locale': time_locale,
            'datetime_str': date_time,
            'duration_str': duration,
            'duration': float(duration),
            'staff_user': request.env['res.users'].browse(int(staff_user_id)),
            'timezone': request.session.get('timezone') or appointment_type.appointment_tz,  # bw compatibility
            'users_possible': self._get_possible_staff_users(appointment_type, json.loads(kwargs.get('filter_staff_user_ids') or '[]')),
        })
        
    
    @has_logged
    @route(['/appointment/<int:appointment_type_id>'],
           type='http', auth="public", website=True, sitemap=True)
    def appointment_type_page(self, appointment_type_id, state=False, staff_user_id=False, **kwargs):
       res = super().appointment_type_page(appointment_type_id, state=False, staff_user_id=False, **kwargs)
       return res
    
    @has_logged
    @http.route(['/appointment/<int:appointment_type_id>/submit'],
                type='http', auth="public", website=True, methods=["POST"])
    def appointment_form_submit(self, appointment_type_id, datetime_str, duration_str, staff_user_id, name, phone, email, prefix_vat, vat, customer_id=None, **kwargs):
        """
        Create the event for the appointment and redirect on the validation page with a summary of the appointment.

        :param appointment_type_id: the appointment type id related
        :param datetime_str: the string representing the datetime
        :param staff_user_id: the user selected for the appointment
        :param name: the name of the user sets in the form
        :param phone: the phone of the user sets in the form
        :param email: the email of the user sets in the form
        """
        appointment_type = self._fetch_and_check_private_appointment_types(
            kwargs.get('filter_appointment_type_ids'),
            kwargs.get('filter_staff_user_ids'),
            kwargs.get('invite_token'),
            current_appointment_type_id=int(appointment_type_id),
        )

        if not appointment_type:
            raise NotFound()
        timezone = request.session.get('timezone') or appointment_type.appointment_tz
        tz_session = pytz.timezone(timezone)
        date_start = tz_session.localize(fields.Datetime.from_string(datetime_str)).astimezone(pytz.utc).replace(tzinfo=None)
        duration = float(duration_str)
        date_end = date_start + relativedelta(hours=duration)
        invite_token = kwargs.get('invite_token')

        # check availability of the selected user again (in case someone else booked while the client was entering the form)
        staff_user = request.env['res.users'].sudo().browse(int(staff_user_id)).exists()
        if staff_user not in appointment_type.sudo().staff_user_ids:
            raise NotFound()
        if staff_user and not staff_user.partner_id.calendar_verify_availability(date_start, date_end):
            return request.redirect('/appointment/%s?%s' % (appointment_type.id, keep_query('*', state='failed-staff-user')))
        
        Partner = self._get_customer_partner() or request.env['res.partner'].sudo().search([('vat', '=', vat)], limit=1)
        if customer_id is not None:
            if customer_id:
                Partner = request.env['res.partner'].sudo().browse(int(customer_id))
           
        if Partner:
            if not Partner.calendar_verify_availability(date_start, date_end):
                return request.redirect('/appointment/%s?%s' % (appointment_type.id, keep_query('*', state='failed-partner')))
            if not Partner.phone:
                Partner.write({'phone': phone})
            if not Partner.email:
                Partner.write({'email': email})
            if not Partner.prefix_vat:
                Partner.write({'prefix_vat': prefix_vat})
            if not Partner.vat:
                Partner.write({'vat': vat})
        else:
            Partner = Partner.create({
                'name': name,
                'phone': Partner._phone_format(phone, country=self._get_customer_country()),
                'email': email,
                "prefix_vat": prefix_vat,
                "vat": vat,
                'lang': request.lang.code,
            })

        # partner_inputs dictionary structures all answer inputs received on the appointment submission: key is question id, value
        # is answer id (as string) for choice questions, text input for text questions, array of ids for multiple choice questions.
        partner_inputs = {}
        appointment_question_ids = appointment_type.question_ids.ids
        for k_key, k_value in [item for item in kwargs.items() if item[1]]:
            question_id_str = re.match(r"\bquestion_([0-9]+)\b", k_key)
            if question_id_str and int(question_id_str.group(1)) in appointment_question_ids:
                partner_inputs[int(question_id_str.group(1))] = k_value
                continue
            checkbox_ids_str = re.match(r"\bquestion_([0-9]+)_answer_([0-9]+)\b", k_key)
            if checkbox_ids_str:
                question_id, answer_id = [int(checkbox_ids_str.group(1)), int(checkbox_ids_str.group(2))]
                if question_id in appointment_question_ids:
                    partner_inputs[question_id] = partner_inputs.get(question_id, []) + [answer_id]

        # The answer inputs will be created in _prepare_calendar_values from the values in question_answer_inputs
        question_answer_inputs = []
        base_answer_input_vals = {
            'appointment_type_id': appointment_type.id,
            'partner_id': Partner.id,
        }
        description_bits = []
        description = ''

        if phone:
            description_bits.append(_('Phone: %s', phone))
        if email:
            description_bits.append(_('Email: %s', email))

        for question in appointment_type.question_ids.filtered(lambda question: question.id in partner_inputs.keys()):
            if question.question_type == 'checkbox':
                answers = question.answer_ids.filtered(lambda answer: answer.id in partner_inputs[question.id])
                question_answer_inputs.extend([
                    dict(base_answer_input_vals, question_id=question.id, value_answer_id=answer.id) for answer in answers
                ])
                description_bits.append('%s: %s' % (question.name, ', '.join(answers.mapped('name'))))
            elif question.question_type in ['select', 'radio']:
                question_answer_inputs.append(
                    dict(base_answer_input_vals, question_id=question.id, value_answer_id=int(partner_inputs[question.id]))
                )
                selected_answer = question.answer_ids.filtered(lambda answer: answer.id == int(partner_inputs[question.id]))
                description_bits.append('%s: %s' % (question.name, selected_answer.name))
            elif question.question_type == 'char':
                question_answer_inputs.append(
                    dict(base_answer_input_vals, question_id=question.id, value_text_box=partner_inputs[question.id].strip())
                )
                description_bits.append('%s: %s' % (question.name, partner_inputs[question.id].strip()))
            elif question.question_type == 'text':
                question_answer_inputs.append(
                    dict(base_answer_input_vals, question_id=question.id, value_text_box=partner_inputs[question.id].strip())
                )
                description_bits.append('%s:<br/>%s' % (question.name, plaintext2html(partner_inputs[question.id].strip())))

        if description_bits:
            description = '<ul>' + ''.join(['<li>%s</li>' % bit for bit in description_bits]) + '</ul>'

        # FIXME AWA/TDE double check this and/or write some tests to ensure behavior
        # The 'mail_notify_author' is only placed here and not in 'calendar.attendee#_send_mail_to_attendees'
        # Because we only want to notify the author in the context of Online Appointments
        # When creating a meeting from your own calendar in the backend, there is no need to notify yourself
        event = request.env['calendar.event'].with_context(
            mail_notify_author=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,       
            is_internal_user = request.env.user.has_group('base.group_user'),
            allowed_company_ids=staff_user.company_ids.ids,
        ).sudo().create(
            self._prepare_calendar_values(appointment_type, date_start, date_end, duration, description, question_answer_inputs, name, staff_user, Partner, invite_token)
        )

        data = {
            'product_id': kwargs.get("product_id", None),
            'duration': kwargs.get("duration", 0)
        }

        event.attendee_ids.write({'state': 'accepted'})

        event.sudo().create_invoices(data)

        return request.redirect('/calendar/view/%s?partner_id=%s&%s' % (event.access_token, Partner.id, keep_query('*', state='new')))
