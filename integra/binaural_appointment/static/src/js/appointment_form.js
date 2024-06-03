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

                    const readonly_css = (value) => {
                        if (value) return  {'opacity': 0.6};

                        return {'opacity': 1};
                    }

                    const {vat, prefix_vat, name, phone, email} = data;

                    // Adding disable style
                    $('#prefix_vat').css({
                        'pointer-events': Boolean(vat) ? 'none': 'all',
                        ...readonly_css(Boolean(vat))
                    });
                    $('#vat').css(readonly_css(Boolean(vat)));
                    $('input[name="name"]').css(readonly_css(Boolean(name)));;
                    $('input[name="phone"]').css(readonly_css(Boolean(phone)));;
                    $('input[name="email"]').css(readonly_css(Boolean(email)));;
                    
                    // Actualiza los campos en tu formulario con la información recibida
                    $('#prefix_vat').val(prefix_vat || '');
                    $('#vat').val(vat || '').attr('readonly', Boolean(vat));
                    $('input[name="name"]').val(name || '').attr('readonly', Boolean(name));
                    $('input[name="phone"]').val(phone || '').attr('readonly', Boolean(phone));
                    $('input[name="email"]').val(email || '').attr('readonly', Boolean(email));




                });
            }
        },

    });

});