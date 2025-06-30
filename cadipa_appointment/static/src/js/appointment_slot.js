/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

const Parent = publicWidget.registry.appointmentSlotSelect;

Parent.include({
    events: Object.assign({}, Parent.prototype.events, {
        'click .o_slot_hours': '_cadipaOnClickHour',
        'click #cadipaConfirmSlotsBtn': '_cadipaConfirmSelection',
    }),

    init() {
        this._super(...arguments);
        this.selectedSlots = [];
    },

    _cadipaOnClickHour(ev) {
        ev.preventDefault();
        const $btn = $(ev.currentTarget).toggleClass('active');

        const slotDate = $btn.attr('data-slot-date');

        const raw = $btn.attr('data-url-parameters')?.replace(/&amp;/g, '&');
        const urlParams = decodeURIComponent(raw || '').replace(/&$/, '');

        const key = `${slotDate}|${urlParams}`;

        if ($btn.hasClass('active')) {
            this.selectedSlots.push({ slotDate, urlParams, key });
        } else {
            this.selectedSlots = this.selectedSlots.filter(s => s.key !== key);
        }

        this.$('#cadipaSelectedSlotsCount').text(this.selectedSlots.length);
        this.$('#cadipaConfirmSlotsBtn').toggleClass('d-none', !this.selectedSlots.length);
    },

    _cadipaConfirmSelection() {
        if (!this.selectedSlots.length) { return; }

        const appointmentTypeID = this.$("input[name='appointment_type_id']").val();
        const first = this.selectedSlots[0];

        const url = new URL(
            `/appointment/${encodeURIComponent(appointmentTypeID)}/info?${first.urlParams}`,
            window.location.origin
        );
        url.searchParams.set(
            'multi_slots',
            JSON.stringify(this.selectedSlots.map(s => s.urlParams))
        );

        const $form = $('<form>', { method: 'GET', action: url.toString() });
        $('<input>', {
            type:  'hidden',
            name:  'multi_slots',
            value: url.searchParams.get('multi_slots'),
        }).appendTo($form);

        const csrf = this.$("input[name='csrf_token']").val();
        if (csrf) {
            $('<input>', { type: 'hidden', name: 'csrf_token', value: csrf }).appendTo($form);
        }

        $('body').append($form);
        $form[0].submit();
    },
});
