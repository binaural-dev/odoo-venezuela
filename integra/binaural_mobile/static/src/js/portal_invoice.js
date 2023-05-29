odoo.define('binaural_mobile.portal_invoices_seller', function(require) {
    'use strict';

    const publicWidget = require('web.public.widget');
    const ajax = require('web.ajax');
    const { _t } = require('web.core');

    publicWidget.registry.portalInvoicesSeller = publicWidget.Widget.extend({
        selector: '.o_portal_invoices_seller',
        events: {
            "click #dowload-NV": "_onDownloadPDFInvoice",
        },
        start: function() {

        },
        _onDownloadPDFInvoice: function(ev) {
            const invoice_name = $("#invoice_name").text()
            const invoice_id = parseInt($("#invoice_id").val())
            var url = ""
            url = "/report/pdf/binaural_invoice.template_invoice_sale_note_binaural_invoice/" + invoice_id //type= NV
            const downloadLink = document.createElement('a');
            downloadLink.href = url;
            downloadLink.download = invoice_name +'.pdf';
            downloadLink.click();
        },

    });
});