/** @odoo-module */

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.PaymentsInfoPortal = publicWidget.Widget.extend({
    selector: '.payments_info_portal',
    events:{
        "click #cancel_payment": "_onClickCancelPayment",
    },
    start: function(){

    },

    _onClickCancelPayment: async function(ev){
        $("#cancel_payment").attr("disabled", true)
        const invoices = await jsonrpc('/payments/cancel_payment', 'call', {
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