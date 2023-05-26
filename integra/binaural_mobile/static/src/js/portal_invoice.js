odoo.define('binaural_mobile.portal_invoices_seller', function(require) {
    'use strict';

    const publicWidget = require('web.public.widget');
    const ajax = require('web.ajax');
    const { _t } = require('web.core');

    publicWidget.registry.portalInvoicesSeller = publicWidget.Widget.extend({
        selector: '.o_portal_invoices_seller',
        events: {
            "click #dowload_pdf_invoice": "_onDownloadPDFInvoice",
        },
        start: function() {

        },
        _onDownloadPDFInvoice: function(ev) {
            // var invoice_id = $(ev.currentTarget).attr('data-id');
            // ajax.jsonRpc('/my/invoices/' + invoice_id + '/pdf', 'call', {}).then(function(action) {
            //     if (action) {
            //         self.do_action(action);
            //     }
            // });
            // const invoice_name = $("#invoice_name").text()
            // const invoice_id = parseInt($("#invoice_id").val())
            // const session_id = this._generateUUID();
            // var url = ""
            // if(invoice_name.substring(0, 2) == 'NE'){
            //     url = `/my/invoices/${invoice_id}?access_token=${session_id}&report_type=pdf&download=true` //type= NV
            // }else {
            //     url = `/my/invoices/${invoice_id}?access_token=${session_id}&report_type=pdf&download=true` //type= FC
            // }
            // const downloadLink = document.createElement('a');
            // downloadLink.href = url;
            // downloadLink.download = 'myfile.html';
            // downloadLink.click();

        },

        _generateUUID: function() {
            return "xxxxxxxx-xxxx-4xxx-xxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
            const r = (Math.random() * 16) | 0, v = c == "x" ? r : (r & 0x3) | 0x8;
            return v.toString(16);
            });
        },

    });
});