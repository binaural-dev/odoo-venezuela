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
       auth='public', type='http', website=True, methods=['POST'], priority=400)
    def appointment_form_submit(self, appointment_type_id, multi_slots=None, **post):
        if not multi_slots:
            return super().appointment_form_submit(appointment_type_id, **post)

        slots = sorted((_parse_slot(q) for q in json.loads(multi_slots)), key=lambda s: s[0])

        time_ranges = []
        range_start, duration_first = slots[0][0], slots[0][1]
        range_end = range_start + relativedelta(hours=duration_first)
        total_hours = duration_first

        for slot_start, slot_duration, _ in slots[1:]:
            next_end = slot_start + relativedelta(hours=slot_duration)
            total_hours += slot_duration
            if slot_start == range_end:
                range_end = next_end
            else:
                time_ranges.append((range_start, range_end))
                range_start, range_end = slot_start, next_end
        time_ranges.append((range_start, range_end))

        timezone = pytz.timezone(request.session.get('timezone', post.get('appointment_tz', 'UTC')))
        locale = request.env.context.get('lang', 'es_ES')

        date_str = format_datetime(time_ranges[0][0].astimezone(timezone),
                                "EEE d MMM y", tzinfo=timezone, locale=locale)
        hours_str = ", ".join(
            f"{start.strftime('%H:%M')} – {end.strftime('%H:%M')}"
            for start, end in time_ranges
        )
        time_locale_str = f"{date_str} {hours_str}"


        redir = None
        for start, end in time_ranges:
            single_duration = (end - start).total_seconds() / 3600.0
            single_post = post.copy()
            single_post.update({
                'datetime_str': fields.Datetime.to_string(start),
                'duration': single_duration,
                'duration_str': single_duration,
            })
            redir = super().appointment_form_submit(appointment_type_id, **single_post)

        if redir and redir.location:
            parsed_url = url_parse(redir.location)
            query_params = parsed_url.decode_query()
            query_params.update({
                'duration_str': total_hours,
                'time_locale': time_locale_str,
            })
            new_url = url_unparse(parsed_url._replace(query=url_encode(query_params)))
            redir.location = new_url

        return redir