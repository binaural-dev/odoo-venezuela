odoo.define('cadipa_reservation_calendar.cadipa_reservation_calendar', function(require) {
  'use strict';

  const publicWidget = require('web.public.widget');
  const ajax = require('web.ajax');
  const { _t } = require('web.core');
  var Dialog = require('web.Dialog');

  const websiteReservationCalendar = publicWidget.Widget.extend({
    selector: '.o_calendar_cadipa',
    events: {
      'click #btn-refresh': '_onRefresh',
      'change .court-chk': '_onRefresh',
      'click .js-reservation-click': '_onReservationClick',
      'click #btn-prev-day': '_onNavigateDay',
      'click #btn-next-day': '_onNavigateDay',
      'click #btn-open-datepicker': '_onOpenDatePicker',
      'change #calendarDatePicker': '_onDateChange',
    },

    init: function(parent, options) {
      this._super(parent, options);
    this.selectedCourts = [];
    this.currentDate = moment();

    },

    start: async function() {
      this.$('#calendarDatePicker').val(this.currentDate.format('YYYY-MM-DD'));
      this.$('#calendarDatePicker').datepicker({
        dateFormat: 'yy-mm-dd',
        onSelect: (dateText, inst) => {
          this._onDateChange();
        },
      });

      this.BuildTableCalendar();
    },

    _onRefresh () {
      this.selectedCourts = $('.court-chk:checked').map((_, el) => el.value).get();
      this.BuildTableCalendar();
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

      // Rellenar el modal con la información
      $('#modalCourtName').text(courtName);
      $('#modalPartnerName').text(partnerName);
      $('#modalReservationTime').text(`${startTime} - ${stopTime}`);
      $('#modalDescription').text(description);
      
      $('#reservationDetailsModal').modal('show');
    },
_onNavigateDay: function(ev) {
  const $target = $(ev.currentTarget);
  if ($target.is('#btn-prev-day')) {
    this.currentDate.subtract(1, 'days');
  } else if ($target.is('#btn-next-day')) {
    this.currentDate.add(1, 'days'); 
  }
  this.$('#calendarDatePicker').val(this.currentDate.format('YYYY-MM-DD'));
  this.BuildTableCalendar();
},

_onOpenDatePicker: function() {
  this.$('#calendarDatePicker').datepicker('show');
},
_onDateChange: function() {
  const selectedDateStr = this.$('#calendarDatePicker').val();
  this.currentDate = moment(selectedDateStr);

  this.BuildTableCalendar(); // Recargar el calendario con la nueva fecha
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

  if (period === 'PM' && hours !== '12') {
    hours = parseInt(hours, 10) + 12;
  } else if (period === 'AM' && hours === '12') {
    hours = '00';
  }
  return hours.toString().padStart(2, '0');
},



  async _searchReservations (courtIds) {
      const searchDate = this.currentDate.format('YYYY-MM-DD');

      const res = await ajax.jsonRpc('/get_reservations', 'call', {
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
      const reservations = await ajax.jsonRpc('/get_reservations_made', 'call', {});
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


    // Construccion de Columna de horas disponibles 
  _createColumnsHours: async function () {
  const resp         = await ajax.jsonRpc('/get_opening_and_closing_time', 'call', {});
  const { open, close } = resp;

  let hoursCol  = '<div class="timesheet__col timesheet__col-time">';
  let hourKeys  = [];                 // ← NUEVO
  for (let h = +open; h < +close; h++) {
    const key   = h.toString().padStart(2, '0'); // 00-23
    const ampm  = h < 12 ? 'am' : 'pm';
    const show  = (h % 12 || 12) + ':00 ' + ampm;
    hoursCol   += `<div class="timesheet__block fw-bold" data-hour="${key}">${show}</div>`;
    hourKeys.push(key);
  }
  hoursCol += '</div>';
  return [hoursCol, hourKeys];
},

    _BuildColumnsWithReservationZone: async function (zones, hourKeys) {
        const fullColumnsHtml = await this._BuildPartnersInColumns(zones, hourKeys);
        return fullColumnsHtml;
    },

    _BuildPartnersInColumns: async function(zones, hourKeys) {
      const partners = await this._searchReservationsPartners();
      let htmlOutput = '';

      zones.forEach(zone => {
        let columnHtml = `<div class="timesheet__col" data-reservation="${zone.id}" data-court="${zone.id}">`;

        hourKeys.forEach(k => {
          const calendarHourKey = k.padStart(2, '0');

            // Filtrar las reservas que coinciden con la cancha actual Y el formato de hora en 24 horas convertido
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

  return websiteReservationCalendar;
});
