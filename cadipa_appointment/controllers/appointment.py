from odoo.addons.binaural_appointment.controllers.appointment import (
    AppointmentController
)
from urllib.parse import parse_qs, unquote_plus
from odoo.http import route, request
from odoo import fields
from dateutil.relativedelta import relativedelta
import json, pytz, logging
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

        # ────────────────────── · MULTI-SLOTS ──────────────────────
        multi_raw  = kwargs.get('multi_slots')
        multi_list = json.loads(multi_raw) if multi_raw else []

        if multi_list:
            first_dt, first_dur, first_params = _parse_slot(multi_list[0])

            date_time             = date_time  or fields.Datetime.to_string(first_dt)
            duration              = duration   or str(first_dur)
            staff_user_id         = staff_user_id         or first_params.get('staff_user_id')
            resource_selected_id  = resource_selected_id  or first_params.get('resource_selected_id')
            available_resource_ids = available_resource_ids or first_params.get('available_resource_ids')
            asked_capacity        = asked_capacity or first_params.get('asked_capacity', 1)

        clean_kwargs = kwargs.copy()
        for dup in (
            'staff_user_id', 'resource_selected_id',
            'available_resource_ids', 'asked_capacity',
        ):
            clean_kwargs.pop(dup, None)

        # ────────────────────── · SUPER (binaural) ─────────────────
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
            # Parse and sort the slots by start datetime
            slots = sorted((_parse_slot(q) for q in multi_list),
                   key=lambda slot: slot[0])

            # Determine the timezone to use
            timezone = pytz.timezone(
            request.session.get(
                'timezone',
                resp.qcontext['appointment_type'].appointment_tz
            )
            )

            format_time = lambda dt: fields.Datetime.to_string(dt.astimezone(timezone))[11:16]

            time_ranges = []
            range_start, duration = slots[0][0], slots[0][1]
            range_end = range_start + relativedelta(hours=duration)
            for slot_start, slot_duration, _ in slots[1:]:
                next_end = slot_start + relativedelta(hours=slot_duration)
            if slot_start == range_end:
                range_end = next_end
            else:
                time_ranges.append((range_start, range_end))
                range_start, range_end = slot_start, next_end
            time_ranges.append((range_start, range_end))

            resp.qcontext.update({
            'time_locale': ", ".join(f"{format_time(start)} – {format_time(end)}"
                         for start, end in time_ranges),
            'multi_slots_json': multi_raw,
            })
            if multi_list:
                total_hours = (time_ranges[-1][1] - time_ranges[0][0]).total_seconds() / 3600.0

                resp.qcontext.update({
                    'time_locale': ", ".join(f"{format_time(start)} – {format_time(end)}" for start, end in time_ranges),
                    'multi_slots_json': multi_raw,
                    'datetime_str': fields.Datetime.to_string(time_ranges[0][0]),
                    'duration_str': str(total_hours),
                })
        return resp
    

    @route(['/appointment/<int:appointment_type_id>/submit'],
           auth='public', type='http', website=True, methods=['POST'], priority=400)
    def appointment_form_submit(self, appointment_type_id, multi_slots=None, **post):
        """
        • Without multi_slots  ->  original flow (super)
        • With multi_slots     ->  one or more events depending on gaps
        """
        if not multi_slots:
            return super().appointment_form_submit(appointment_type_id, **post)

        slots = sorted((_parse_slot(q) for q in json.loads(multi_slots)), key=lambda s: s[0])

        contiguous = all(
            slots[i][0] + relativedelta(hours=slots[i][1]) == slots[i+1][0]
            for i in range(len(slots)-1)
        )

        if contiguous:
            first = slots[0][0]
            last  = slots[-1][0] + relativedelta(hours=slots[-1][1])
            post.update({
                'datetime_str': fields.Datetime.to_string(first),
                'duration_str': str((last - first).total_seconds() / 3600.0),
            })
            return super().appointment_form_submit(appointment_type_id, **post)

        redir = None
        for date, duration, _ in slots:
            single = post.copy()
            single.update({
                'datetime_str': fields.Datetime.to_string(date),
                'duration_str': str(duration),
            })
            redir = super().appointment_form_submit(appointment_type_id, **single)
        return redir
    
    