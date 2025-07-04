/** @odoo-module **/
import publicWidget from '@web/legacy/js/public/public_widget';
import { jsonrpc } from '@web/core/network/rpc_service';
import { _t } from '@web/core/l10n/translation';
import Dialog from '@web/core/dialog/dialog';

const websiteReservationCalendar = publicWidget.Widget.extend({
  selector: '.o_calendar_cadipa',
  events: {
    'click #btn-apply-filter': '_onRefresh',
    'click #btn-select-all': '_onSelectAll',


    'click #btn-refresh': '_onRefresh',
    'change .court-chk': '_onRefresh',
    'click .js-reservation-click': '_onReservationClick',
    'click #btn-prev-day': '_onNavigateDay',
    'click #btn-next-day': '_onNavigateDay',
    'change #calendarDatePicker': '_onDateChange',
  },

  init: function(parent, options) {
    this._super(parent, options);
    this.selectedCourts = [];
    this.currentDate = new Date();
  },

  start: async function() {
    this.$('#calendarDatePicker').val(this.formatDate(this.currentDate));
    this.BuildTableCalendar();
  },

  _onRefresh () {
    this.selectedCourts = $('.court-chk:checked').map((_, el) => el.value).get();
    this.BuildTableCalendar();
  },
  _onSelectAll() {
    this.el.querySelectorAll('.court-chk').forEach(cb => cb.checked = true);
},


  _onReservationClick: function(ev) {
    const $target = $(ev.currentTarget);

    const reservationId = $target.data('reservation-id');
    const partnerName = $target.data('partner-name');
    const startTime = $target.data('start-time');
    const stopTime = $target.data('stop-time');
    const courtName = $target.data('court-name');
    const courtId = $target.data('court-id');
    const description = $target.data('description');

    $('#modalCourtName').text(courtName);
    $('#modalPartnerName').text(partnerName);
    $('#modalReservationTime').text(`${startTime} - ${stopTime}`);
    let formattedDescription = '';
        if (description) {
            const lines = description.split('\n').map(line => line.trim()).filter(line => line.length > 0);
            if (lines.length > 0) {
                formattedDescription = '<ul>' + lines.map(line => `<li>${line}</li>`).join('') + '</ul>';
            } else {
                formattedDescription = `<p>${description}</p>`;
            }
        } else {
            formattedDescription = '<p>No hay descripción disponible.</p>';
        }

        $('#modalDescription').html(formattedDescription);

    $('#reservationDetailsModal').modal('show');
  },
  _onNavigateDay: function(ev) {
    const $target = $(ev.currentTarget);
    if ($target.is('#btn-prev-day')) {
      this.currentDate.setDate(this.currentDate.getDate() - 1);
    } else if ($target.is('#btn-next-day')) {
      this.currentDate.setDate(this.currentDate.getDate() + 1);
    }
    this.$('#calendarDatePicker').val(this.formatDate(this.currentDate));
    this.BuildTableCalendar();
  },

  _onDateChange: function() {
    const selectedDateStr = this.$('#calendarDatePicker').val();
    this.currentDate = new Date(selectedDateStr);

    this.BuildTableCalendar();
  },

  BuildTableCalendar: async function() {
    const Calendar = $('#content-reservation-calendar');
    const reservation = await this._searchReservations(this.selectedCourts);
    if (!reservation || reservation.length === 0) {
      Dialog.alert(this, _t("No hay reservas disponibles para esta cancha."), { title: 'Info' });
      Calendar.empty();
      return;
    }

    let MainTable = '<div class="timesheet">';
    let headerTable = await this._BuildHeaderTable(reservation);

    headerTable += MainTable;
    let columnsHours = await this._createColumnsHours();
    headerTable += columnsHours[0];
    const columnsWithReservationsAndPartners = await this._BuildColumnsWithReservationZone(reservation, columnsHours[1]);
    headerTable += columnsWithReservationsAndPartners;
    Calendar.empty();
    Calendar.append(headerTable);
  },

  filterByCourt: function () {
      this.selectedCourts = $('#court-filter').val() || [];
      this.BuildTableCalendar();
  },

  convertTo24Hour: function(time12h) {
    const [time, period] = time12h.split(' ');
    let [hours, minutes] = time.split(':');

    if (period && period.toUpperCase() === 'PM' && hours !== '12') {
      hours = parseInt(hours, 10) + 12;
    } else if (period && period.toUpperCase() === 'AM' && hours === '12') {
      hours = '00';
    }
    return hours.toString().padStart(2, '0');
  },

  // Helper function to format Date object to YYYY-MM-DD
  formatDate: function(date) {
    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    return `${year}-${month}-${day}`;
  },
  /* Returns minutes since the court opening */
_getMinuteOffset(time12h, openingHour) {
    /* time12h p.ej. "11:30 AM" */
    const [hhmm, period] = time12h.split(' ');
    let [h, m] = hhmm.split(':').map(Number);
    if (period.toUpperCase() === 'PM' && h !== 12) h += 12;
    if (period.toUpperCase() === 'AM' && h === 12) h  = 0;
    return (h - openingHour) * 60 + m;
},
_getDuration(start12h, stop12h) {
    const toMin = (t) => {
        const [hm, per] = t.split(' ');
        let [h, m] = hm.split(':').map(Number);
        if (per.toUpperCase() === 'PM' && h !== 12) h += 12;
        if (per.toUpperCase() === 'AM' && h === 12) h  = 0;
        return h*60 + m;
    };
    return toMin(stop12h) - toMin(start12h);
},


  async _searchReservations (courtIds) {
      const searchDate = this.formatDate(this.currentDate);

      const res = await jsonrpc('/get_reservations',{
        court_ids: courtIds,
        date: searchDate,
      });
      if (res.status === 400) {
        Dialog.alert(this, res.msg, { title: 'Error' });
        return [];
      }
      return res.reservation || [];
    },

_searchReservationsPartners: async function() {
    // Get the current date from the instance
    const searchDate = this.formatDate(this.currentDate); // Use the current date

    const reservations = await jsonrpc('/get_reservations_made',{
        date: searchDate,
    });
    const { status: st, msg, reservation_partners } = reservations;
    const is400 = st === 400;
    if (is400) {
        Dialog.alert(this, msg, { title: 'Error' });
        return [];
    }
    return reservation_partners;
},

    _BuildHeaderTable: async function (zones) {
      let html = `
        <div class="timesheet">
          <div class="timesheet__col timesheet__col-time">
            <div class="timesheet__block-header" data-time="0"></div>
          </div>`;
      zones.forEach(z => {
        html += `
          <div class="timesheet__col" data-reservation="${z.id}">
            <div class="fw-bold timesheet__block-header">
              <p class="text-capitalize lh-1">${z.name}</p>
            </div>
          </div>`;
      });
      html += '</div>';
      return html;
    },

    _createColumnsHours: async function () {
      const resp         = await jsonrpc('/get_opening_and_closing_time');
      const { open, close } = resp;

      let hoursCol  = '<div class="timesheet__col timesheet__col-time">';
      let hourKeys  = [];
      for (let h = +open; h <= +close; h++) {
        const key   = h.toString().padStart(2, '0');
        const ampm  = h < 12 ? 'am' : 'pm';
        const show  = (h % 12 || 12) + ':00 ' + ampm;
        hoursCol   += `<div class="timesheet__block fw-bold" data-hour="${key}">${show}</div>`;
        hourKeys.push(key);
      }
      hoursCol += '</div>';
      return [hoursCol, hourKeys];
    },

    _BuildColumnsWithReservationZone: async function (zones, hourKeys) {
    const partners = await this._searchReservationsPartners();
    const { open, close } = await jsonrpc('/get_opening_and_closing_time');
    const minutesTotal = (close - open) * 60;
    let html = '';

    zones.forEach(zone => {
        let col = `<div class="timesheet__col" data-court="${zone.id}">`;
        hourKeys.forEach(k => {
            col += `<div class="timesheet__block" data-hour="${k}"></div>`;
        });

        const resForCourt = partners.filter(p => p.appointment_type_id.id === zone.id);
        resForCourt.forEach(r => {
            const offsetMin = this._getMinuteOffset(r.start, +open);
            const durMin    = this._getDuration(r.start, r.stop);

            const topPct    = offsetMin  / minutesTotal * 100;
            const hPct      = durMin     / minutesTotal * 100;

            col += `
              <div class="schedule bg-primary js-reservation-click"
                   style="top:${topPct}%; height:${hPct}%"
                   data-reservation-id="${r.id}"
                   data-partner-name="${r.partner_id.name}"
                   data-start-time="${r.start}"
                   data-stop-time="${r.stop}"
                   data-court-name="${zone.name}"
                   data-court-id="${zone.id}"
                   data-description="${r.description}">
                   <strong>${r.start} - ${r.stop}</strong><br/>
                   ${r.partner_id.name}
              </div>`;
        });

        col += '</div>';
        html += col;
    });
    return html;
},

    _BuildPartnersInColumns: async function(zones, hourKeys) {
      const partners = await this._searchReservationsPartners();
      let htmlOutput = '';

      zones.forEach(zone => {
        let columnHtml = `<div class="timesheet__col" data-reservation="${zone.id}" data-court="${zone.id}">`;

        hourKeys.forEach(k => {
          const calendarHourKey = k.padStart(2, '0');

          const reservationForSlot = partners.find(p => {
            const reservation24Hour = this.convertTo24Hour(p.start);
            return p.appointment_type_id.id === zone.id && reservation24Hour === calendarHourKey;
          });

          if (reservationForSlot) {
            columnHtml += `
              <div class="timesheet__block" data-court="${zone.id}" data-hour="${k}">
                <div class="schedule bg-primary text-white mb-1 js-reservation-click"
                     data-reservation-id="${reservationForSlot.id}"
                     data-partner-name="${reservationForSlot.partner_id.name}"
                     data-start-time="${reservationForSlot.start}"
                     data-stop-time="${reservationForSlot.stop}"
                     data-court-name="${zone.name}"
                     data-court-id="${zone.id}"
                     data-description="${reservationForSlot.description}"> <strong>${reservationForSlot.start} - ${reservationForSlot.stop}</strong><br>
                  ${reservationForSlot.partner_id.name}
                </div>
              </div>`;
          } else {
            columnHtml += `<div class="timesheet__block" data-hour="${k}" data-court="${zone.id}"></div>`;
          }
        });
        columnHtml += '</div>';
        htmlOutput += columnHtml;
      });

      return htmlOutput;
    },
});

publicWidget.registry.websiteReservationCalendar = websiteReservationCalendar;