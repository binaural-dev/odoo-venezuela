odoo.define('binaural_mobile.payments_info_portal', function(require) {
    'use strict';

    const publicWidget = require('web.public.widget');
    const ajax = require('web.ajax');
    const { _t } = require('web.core');

    publicWidget.registry.PaymentsInfoPortal = publicWidget.Widget.extend({
        selector: '.payments_info_portal',
        events:{
            "click #cancel_payment": "_onClickCancelPayment",
        },
        start: function(){

        },

        _onClickCancelPayment: async function(ev){
            $("#cancel_payment").attr("disabled", true)
            const invoices = await ajax.jsonRpc('/payments/cancel_payment', 'call', {
                "payment": +$("#payment_id").val(),
            })
            const {status} = invoices
            const is404 = status === 404;
            if(is404){
                $("#cancel_payment").attr("disabled", false)
                alert(status)
                return
            }
            window.location.reload()
        }
    })
})