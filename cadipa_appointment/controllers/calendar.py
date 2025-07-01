import pytz
from babel.dates import format_datetime
from odoo import http, fields
from odoo.http import request, route
from odoo.tools.misc import get_lang
import logging
_logger = logging.getLogger(__name__)

from odoo.addons.appointment.controllers.calendar import (
    AppointmentCalendarController as BaseAppointmentCalendarController
)

class CadipaAppointmentCalendarController(BaseAppointmentCalendarController):

    @route(['/calendar/view/<string:access_token>'], auth='public',
           website=True, type='http')
    def appointment_view(self, access_token, partner_id, state=False, **kw):

        response = super().appointment_view(access_token, partner_id, state, **kw)
        if not isinstance(response, http.Response):
            return response

        qctx   = response.qcontext
        events = request.env['calendar.event'].sudo().search(
            [('access_token', '=', access_token)], order='start'
        )
        if not events:
            qctx['duration_str'] = "N/A"
            return response

        time_locale = kw.get('time_locale')
        duration_str = kw.get('duration_str')

        if time_locale and duration_str:
            qctx.update({
                'time_locale': time_locale,
                'duration_str': duration_str,
                'duration': float(duration_str.split()[0])
            })
            return response

        start_all = min(events.mapped('start'))
        stop_all  = max(events.mapped('stop'))
        hours = (stop_all - start_all).total_seconds() / 3600.0
        qctx.update({'duration': hours, 'duration_str': f"{hours:g} h"})

        ranges = []
        rs, re = events[0].start, events[0].stop
        for ev in events[1:]:
            if ev.start == re:
                re = ev.stop
            else:
                ranges.append((rs, re))
                rs, re = ev.start, ev.stop
        ranges.append((rs, re))

        tz_name  = request.session.get('timezone') or events[0].appointment_type_id.appointment_tz
        timezone = pytz.timezone(tz_name)
        locale   = get_lang(request.env).code or 'en_US'

        date_str = format_datetime(ranges[0][0], "EEE d MMM y", locale=locale, tzinfo=timezone)
        hours_str = ", ".join(
            f"{format_datetime(start, 'H:mm', locale=locale, tzinfo=timezone)} – "
            f"{format_datetime(end, 'H:mm', locale=locale, tzinfo=timezone)}"
            for start, end in ranges
        )

        qctx['time_locale'] = f"{date_str} {hours_str}"

        return response
