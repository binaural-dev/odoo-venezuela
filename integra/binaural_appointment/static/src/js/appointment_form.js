odoo.define('binaural_appointment.appointment_form', function (require) {
    'use strict';

    const publicWidget = require('web.public.widget');
    const ajax = require('web.ajax');
    publicWidget.registry.AppointmentForm = publicWidget.Widget.extend({
        selector: '.appointment_form',
        events: {
            'change #customer_id': '_onChangeCustomerId',
        },

        _onChangeCustomerId: function (ev) {
            var customerId = $(ev.currentTarget).val();
            if (customerId) {
                ajax.jsonRpc('/appointment/get_data_customer', 'call', {
                    customer_id: customerId
                }).then(function (data) {
                    // Actualiza los campos en tu formulario con la información recibida
                    $('#vat').val(data.vat || '').attr('readonly', true);
                    $('#prefix_vat').val(data.prefix_vat || '').attr('readonly', true);
                    $('input[name="name"]').val(data.name || '');
                    $('input[name="phone"]').val(data.phone || '');
                    $('input[name="email"]').val(data.email || '');
                });
            }
        },

    });

});