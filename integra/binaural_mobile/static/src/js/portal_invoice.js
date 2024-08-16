/** @odoo-module */

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { jsonrpc } from "@web/core/network/rpc_service";

publicWidget.registry.portalInvoicesSeller = publicWidget.Widget.extend({
    selector: '.o_portal_invoices_seller',
    events: {
        "click #dowload-invoice": "_onDownloadPDFInvoice",
    },
    start: function() {
        this.buildTaxesInvoice()
    },
    _onDownloadPDFInvoice: function(ev) {
        const invoice_name = $("#invoice_name").text()
        const invoice_id = parseInt($("#invoice_id").val())
        const fiscal = $("#invoice").is(":checked")
        let url = ""
        if(!fiscal){
            url = "/report/pdf/binaural_invoice.template_invoice_sale_note_binaural_invoice/" + invoice_id
        }
        if(fiscal){
            url = "/report/pdf/binaural_invoice.template_invoice_free_form_binaural_invoice/" + invoice_id 
        }
        const downloadLink = document.createElement('a');
        downloadLink.href = url;
        downloadLink.download = invoice_name +'.pdf';
        downloadLink.click();
    },

    buildTaxesInvoice: async function(){
        if ($("#invoice_id").val() == '' || !$("#invoice").prop('checked')) return
        let invoiceId = $("#invoice_id").val(); 
        const products = await jsonrpc('/get_tax_invoices', 'call', {
            "invoice_id" : invoiceId,
        })
        const { status, data } = products;
        const is400 = status === 400;
        if (is400) return

        const symbol = $("#symbolB").val()
        let symbolAfter = ""
        let symbolBefore = ""
        let decimalPlaces = +$("#decimal").val()
        
        if($("#positionS").val() == "after"){
            symbolAfter = symbol
        }else{
            symbolBefore = symbol
        }
        let taxProducts = {}
        for(let key in data){
            let valueIva = parseFloat(data[key]["tax_ids"][2])
            let totalProduct = parseFloat(data[key]["price_subtotal"])

            if (taxProducts[valueIva]) {
                taxProducts[valueIva][0] = parseFloat(taxProducts[valueIva][0]) + (totalProduct / 100 * valueIva)
                taxProducts[valueIva][0] = taxProducts[valueIva][0].toFixed(decimalPlaces)
                taxProducts[valueIva][1] = (parseFloat(taxProducts[valueIva][1]) + totalProduct).toFixed(decimalPlaces) 
            } else {
                if(valueIva == 0) {
                    let total = (0).toFixed(decimalPlaces)
                    taxProducts[valueIva] = [total,totalProduct]
                }
                else{
                    let total = parseFloat((totalProduct / 100 * valueIva)).toFixed(decimalPlaces)
                    taxProducts[valueIva] = [total,totalProduct]
                }
            }
        }
        let taxLabel = ``
        for (let indexLine in taxProducts) {
            let valTax = 0
            let valTotal = 0
            valTax = indexLine == 0 ? valTax.toFixed(decimalPlaces) : taxProducts[indexLine][0];
            valTotal = parseFloat(taxProducts[indexLine][1]).toFixed(decimalPlaces)
            if(indexLine == 0){
                taxLabel += `<div class="d-flex justify-content-end iva-remove">
                                    <label class="form-label" style="padding-right:3px;">BI Exento: </label>
                                    <label style="font-weight: bolder;"> ${symbolBefore} ${valTotal} ${symbolAfter}</label>
                                </div>`
            }else{
                taxLabel += `<div class="d-flex justify-content-end iva-remove">
                                    <label class="form-label" style=" padding-right:3px;">BI G IVA ${indexLine}%:</label>
                                    <label style="font-weight: bolder;"> ${symbolBefore} ${valTotal} ${symbolAfter}</label>
                                </div>`
                taxLabel += `<div class="d-flex justify-content-end iva-remove">
                    <label class="form-label" style="padding-right:3px;">IVA ${indexLine}%:</label>
                    <label style="font-weight: bolder;"> ${symbolBefore} ${valTax} ${symbolAfter}</label>
                </div>`
            }
        }
        $('#taxes-invoices-budgets').html(taxLabel)
    },

});