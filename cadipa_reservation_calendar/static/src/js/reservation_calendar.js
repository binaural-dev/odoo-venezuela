odoo.define('cadipa_reservation_calendar.cadipa_reservation_calendar', function(require) {
  'use strict';

  const publicWidget = require('web.public.widget');
  const ajax = require('web.ajax');
  const { _t } = require('web.core');
  var Dialog = require('web.Dialog');

  const websiteReservationCalendar = publicWidget.Widget.extend({
    selector: '.o_calendar_cadipa',
    events: {
      // "click #test": "_searchReservationsPartners",
      "click #test": "BuildTableCalendar",
    },
    init: function(parent, options) {

    },
    start: async function() {
      // this._createColumnsHours()
    },

    // CALENDARIO TOTAL 
    BuildTableCalendar: async function() {
      const Calendar = $('#content-reservation-calendar');

      const reservation = await this._searchReservations()
      if (!reservation){
        Dialog.alert(this,_t("Not have nothing"), { title: 'Info' });
        return 
      }
      let MainTable = `
        <div class="timesheet">
      `
      let headerTable = await this._BuildHeaderTable(reservation)
      headerTable += MainTable
      let columnsHours = await this._createColumnsHours()
      headerTable += columnsHours[0]

      const columnsWithReservationsAndPartners = await this._BuildColumnsWithReservationZone(reservation, columnsHours[1])
      headerTable += columnsWithReservationsAndPartners
      // headerTable +=MainTable
      Calendar.empty()
      Calendar.append(headerTable)
    },

    // Construccion de header dependiendo las reservas disponibles con productos
    _BuildHeaderTable: async function(reservationZones){
      let columnHeader = `
      <div class="timesheet">
        <div class="timesheet__col timesheet__col-time">
          <div class="timesheet__block-header" data-time="0"/>
        </div>
      `
      reservationZones.forEach(zone => {
        const column = `
          <div class="timesheet__col" data-reservation="${zone.id}">
            <div class="fw-bold timesheet__block-header">
              <p class="text-capitalize lh-1">${zone.name}</p>
            </div>
          </div>
        `;
        columnHeader += column;
      });
      columnHeader += `</div>`
      return columnHeader;
    },

    // Construccion de Columna de horas disponibles 
    _createColumnsHours: async function() {
      let initTable = `
        <div class="timesheet__col timesheet__col-time">
      `
      
      let OCtime = await ajax.jsonRpc('/get_opening_and_closing_time', 'call',{})
      let {open, close} = OCtime;
      let countBlock = 0

      for (let hour = +open; hour < +close; hour++) {
        const hourStr = hour < 10 ? '0' + hour : hour;
        const amPm = hour < 12 ? 'am' : 'pm';
        const displayHour = hour % 12 === 0 ? 12 : hour % 12;

        const majorSlot = `
          <div class="timesheet__block fw-bold" data-time="${hourStr}">${displayHour}:00 ${amPm}</div>
        `;
        initTable += majorSlot;
        countBlock++;
      }
      let closeTable = `</div>`
      initTable += closeTable
      return [initTable,countBlock]
    },

    // Construccion de columnas en area de reservaciones con flotantes de reservaciones
    _BuildColumnsWithReservationZone: async function(reservationZones, countBlock) {
      let reservationColumns = ``;
      let timeBlock = `<div class="timesheet__block"/>`;
      let Blocks = ``;
      for (let hour = 0; hour < countBlock; hour++) {
        Blocks += timeBlock;
      }
      const reservationPartners = await this._searchReservationsPartners();
      const reservation_ids = reservationZones.map(line => line.id);
      let infoPartnersInColumns = await this._BuildPartnersInColumns(reservation_ids, reservationPartners);
      
      reservationZones.forEach(zone => {
        let currentColumn = infoPartnersInColumns.filter(column => column.id === zone.id);
        const columnContent = currentColumn.length > 0 ? currentColumn[0].columns : '';
        const column = `
          <div class="timesheet__col" data-reservation="${zone.id}">
            ${Blocks}
            ${columnContent}
          </div>
        `;
        reservationColumns += column;
      });
    
      return reservationColumns;
    },

    // Reservacioones hechas
    _BuildPartnersInColumns: async function(reservation_ids, reservationPartners){
      let tdWithReservations = ``
      let initTd = ``
      let closeTd = `</div>`
      let notPaid = `danger`
      let processPaid = `warning`
      let paid = `success`
      let invoiceDraft = `info`
      let invoiceCancelled = `black`
      let payment_state = ``
      let questionAndAnswer = ``
      let allColumns = []

      reservation_ids.forEach(reservation_id => {
        initTd = ``
        const partnersForReservation = reservationPartners.filter(partner => partner.appointment_type_id.id === reservation_id);
        partnersForReservation.forEach(partner => {
          payment_state = notPaid
          if (partner.invoice){
            if(partner.invoice.state == "posted"){
              if(partner.invoice.payment_state == "paid" || partner.invoice.payment_state == "in_payment"){
                payment_state = paid
              }
              if (partner.invoice.payment_state == "partial"){
                payment_state = processPaid
              }
            }else{
              payment_state = partner.invoice.state == "draft" ? invoiceDraft : invoiceCancelled;
            }
          }
          questionAndAnswer = ``
          if(partner.message.question && partner.message.answer){
            questionAndAnswer = `<span class='fst-italic'>${partner.message.question}</span><br/>${partner.message.answer}`
          }
          initTd += `
            <div data-reservation="${reservation_id}" class="schedule bg-primary">
              <a class="fc-event fc-event-start fc-event-end fc-event-today fc-event-future fc-timegrid-event fc-v-event text-white">
                  <div class="fc-event-time">
                    <strong>${partner.start} - ${partner.stop}</strong> <span class="badge bg-${payment_state}">ㅤ</span><br/>
                    ${partner.partner_id.name}
                  </div>
                  <div
                    class="fc-event-title-container">
                    <div
                      class="fc-event-title fc-sticky">
                      ${questionAndAnswer}
                    </div>
                  </div>
              </a>
            </div>
          `;
        });
        allColumns.push({"id": reservation_id, "columns": initTd})
      });

      return allColumns
    },

    // CALL RPS 
    _searchReservations: async function() {
      const reservations = await ajax.jsonRpc('/get_reservations', 'call',{})
      const { status:st, msg, reservation} = reservations;
      const is400 = st === 400;
      if (is400) {
        Dialog.alert(this,msg, { title: 'Error' });
        return false
      }
      return reservation
    },

    _searchReservationsPartners: async function() {
      const reservations = await ajax.jsonRpc('/get_reservations_made', 'call',{})
      const { status:st, msg, reservation_partners} = reservations;
      const is400 = st === 400;
      if (is400) {
        Dialog.alert(this,msg, { title: 'Error' });
        return false
      }
      return reservation_partners
    },
  });

  publicWidget.registry.websiteReservationCalendar = websiteReservationCalendar

  return websiteReservationCalendar;
});