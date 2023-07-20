odoo.define('binaural_mobile.portal_budget_form', function(require) {
    'use strict';

    const publicWidget = require('web.public.widget');
    const ajax = require('web.ajax');
    const { _t } = require('web.core');
    
    publicWidget.registry.portalBudgetForm = publicWidget.Widget.extend({
        selector: '.o_portal_budget_form',
        events: {
            "keyup #search_text": "_onKeyupSearchText",
            "change #client": "_onChangeClient",
            "click #search_product": "_onClickSearchProduct",
            "click #exit_products": "_onClickExitProducts",
            "click .delete_product": "_onClickDeleteProduct",
            "click #save_products": "_onClickSaveProducts",
            "change #invoice": "_onChangeInvoice",
            "click .cancel-btn": "_onClickCancel",
            "click .confirm-btn": "_onClickConfirm",
            "click #dowload_pdf": "_onClickDowloadPdf",
            "change #same_address": "_onChangeSameAddress",
        },
        init: function(parent, options) {
            this._super.apply(this, arguments);
            this.partners = [];
        },
        start: function() {
            const self = this;

            $('#client').select2({
                maximumInputLength: 35,
                minimumInputLength: 0,
                maximumSelectionSize: 1,
                ajax: {
                    url: '/budget/client',
                    dataType: 'json',
                    data:  term => ({query: term}),
                    results: data => {
                        const ret = [];
                        _.each(data, function (client) {
                            const { id: clientId } = client
                            const isExistclient = ret.find(client => client.id === clientId);

                            if (isExistclient) return;

                            ret.push({
                                id: client.id,
                                text: client.name,
                                isNew: false,
                            });
                            self.partners.push(client); 
                        });
                        return {results: ret};
                    }
                    
                },
            }); 

            $(document).on('input', '.qty_product', function() {
                var valor = $(this).val();
                if (isNaN(valor)) {
                    $(this).val(valor.slice(0, -1));
                }
            });

            this._onChangeSameAddress(true)

        },
        
        _onChangeClient: function(ev) {
            const $addressSelections = $("select.address_selection");
            const labelFee = $("#fee")
            const labelPayTerms = $("#payment_terms")

            const client = selectedPartner(this.partners, parseInt(ev.target.value));
            const { property_product_pricelist, property_payment_term_id } = client;

            $.each($addressSelections, function (index, addressSelection) {
                const $selection = $(addressSelection);
                const addr_type = $selection.data("address");
                const partner_child = getDirection([ ...client.child_ids ], addr_type);
                const address = {
                    id: partner_child.length > 0 ? partner_child[0].id : client.id,
                    street: partner_child.length > 0 ? partner_child[0].street : client.street || "No Apply",
                }
                $selection.empty();
                $selection.append(`<option value="${address.id}">${address.street}</option>`);
            });
            
            labelFee.text(property_product_pricelist.length > 0 ? property_product_pricelist[1] : "")
            $("#fee_value").val(property_product_pricelist.length > 0 ? property_product_pricelist[0] : "")
            labelPayTerms.text(property_payment_term_id.length > 0 ? property_payment_term_id[1] : "").val(property_payment_term_id.length > 0 ? property_payment_term_id[0] : "");
            $("#payment_terms_value").val(property_payment_term_id.length > 0 ? property_payment_term_id[0] : "")
            
            $("#openProduct").attr('disabled', false)
            $("input[id='client']").select2("enable", false);
            $("#invoice").attr('disabled', false)
            $("#same_address").attr('disabled', false)
        },

        _onChangeSameAddress : function(ev) {
            if ($("#same_address").is(':checked')){
                $(".div_shipping").hide()
            }else{
                $(".div_shipping").show()
            }
        },

        _onKeyupSearchText: function(ev) {
            if ($('#search_text').val() == ''){
                $('#search_product').attr('disabled', true)
            }else{
                $('#search_product').attr('disabled', false)
            }
        },

        _onClickSearchProduct: async function(ev) {
            if($('#search_text').val() != ''){
                const product_code = $('#search_text').val()
                $('#search_product').attr('disabled', true)
                $('#search_text').val('')
                const products = await ajax.jsonRpc('/budget/product', 'call', {
                    "product": product_code
                });
                const tbody = $("#table_inside")
                const { status } = JSON.parse(products);
                const is204 = status === 204;
                if (is204){
                    var noFound = _t("No products found with the code or name:")
                    tbody.empty()
                    tbody.append(`
                        <div class="alert alert-primary" style="font-weight: bolder;" role="alert">
                            ${noFound} ${product_code}
                        </div>
                    `)
                    $('#save_products').attr('disabled', true)
                    return
                }
                $('#save_products').attr('disabled', false) 
                const { data } = JSON.parse(products);
                tbody.empty()
                var priceLabel = _t("Price")
                var availableLabel = _t("Available")
                var qtyLabel = _t("Qty")
                var multiplesLabel = _t("Only multiples of")
                data.forEach(product => {
                    const { name, default_code, list_price, qty_available, image, id } = product
                    tbody.append(`
                        <tr>
                            <td class="text-center"><img style="width: auto; height:70px;" src="${image}"/></td>
                            <td colspan="2">
                                <label style="font-weight: bolder;" class="name_product">[${default_code}] ${name}</label><br/>
                                <input type="hidden" class="val_product" value="${id}"/>
                                <label class="form-text">${priceLabel}:</label><label class="form-text price_product" style="font-weight: bolder;">${list_price}</label><br/>
                                <label class="form-text">${availableLabel}:</label><label class="form-text" style="font-weight: bolder;">${qty_available}</label>
                            </td>
                            <td style="width: 150px;">
                                <input type="text" class="form-control qty_product" placeholder="${qtyLabel}"/>
                                <label class="form-text">${multiplesLabel} 1</label>
                            </td>
                        </tr>
                    `)
                });
            }
        },

        _onClickExitProducts: function(ev) {
            $('#save_products').attr('disabled', true)
            $('#search_product').attr('disabled', true)
            $('#search_text').val('')
            $("#table_inside").empty()
        },

        _onClickSaveProducts: function(ev) {
            const queryselector = document.querySelectorAll("#table_inside input.qty_product")
            var id = 0
            var qty = 0
            var price = 0
            var address = 0
            
            queryselector.forEach(async input => {
                if (input.value != ''){ 
                    if($("#same_address").is(':checked')){
                        address = parseInt($("#billing_address").val())
                    }else{
                        address = parseInt($("#project").val())
                    }
                    const tr = $(input).closest('tr');
                    price = tr.find('label.price_product').text()
                    const name = tr.find('label.name_product').text()
                    id = tr.find('input.val_product').val()
                    qty = input.value
                    id = parseInt(id)
                    qty = parseFloat(qty)
                    price = parseFloat(price)
                    if($("#number_order_value").val() == ''){
                        const products = await ajax.jsonRpc('/budget/order/create', 'call', {
                            "sale_order": {
                                "partner_id": parseInt($("#client").val()),
                                "partner_invoice_id": parseInt($("#billing_address").val()),
                                "partner_shipping_id": address,
                                "pricelist_id": parseInt($("#fee_value").val()),
                                "payment_term_id": parseInt($("#payment_terms_value").val()),
                                "order_line": [
                                    {
                                        "product_id": id,
                                        "product_uom_qty": qty,
                                        "price_unit": price,
                                    }
                                ],
                                "note": $("#note").val(),
                            },
                            "tax_included": $("#invoice").is(':checked')
                        })
                        console.log(products)
                        const { status, data } = products;
                        const is400 = status === 400;
                        if (is400) return 
                            
                        $("#note").val("")
                        $("#product_head").show()
                        $("#number").show()
                        $("#number_order").text(data[0].name)
                        $("#number_order_value").val(data[0].id)
                        $("#same_address").attr('disabled', true)
                        this.build_table_products(data)
                    }else{
                        const products = await ajax.jsonRpc('/budget/create/order/line', 'call', {
                            "sale_order": {
                                "id": parseInt($("#number_order_value").val()),
                                "partner_id": parseInt($("#client").val()),
                                "partner_invoice_id": parseInt($("#billing_address").val()),
                                "partner_shipping_id": address,
                                "pricelist_id": parseInt($("#fee_value").val()),
                                "payment_term_id": parseInt($("#payment_terms_value").val()),
                                "order_line": [
                                    {
                                        "product_id": id,
                                        "product_uom_qty": qty,
                                        "price_unit": price,
                                    }
                                ],
                                "note": $("#note").val(),
                            },
                            "tax_included": $("#invoice").is(':checked')
                        })
                        console.log(products)
                        const { status, data } = products;
                        const is400 = status === 400;
                        if (is400) return 
                        $("#note").val("")
                        this.build_table_products(data)
                    }
                }
            })
            this._onClickExitProducts()
            $("#table_inside").empty()
        },

        build_table_products: function(data) {
            const tbody = $("#product_list")
            console.log(data)
            const { order_line } = data[0];
            tbody.empty()
            var qtyLabel = _t("Qty:")
            var unitLabel = _t("Unit price:")
            order_line.forEach(line => {
                const { name, product_uom_qty, price_unit, price_subtotal, id } = line
                tbody.append(`
                <tr>
                    <td colspan="4">
                        <label style="font-weight: bolder;">${name}</label> <input type="hidden" value="${id}"> <br/>
                        <label class="form-label">${qtyLabel}</label><label class="form-label" style="font-weight: bolder;">${product_uom_qty}</label><br/>
                        <label class="form-text">${unitLabel}</label><label class="form-text" style="font-weight: bolder;">${price_unit}</label><br/>
                    </td>
                    <td class="text-center">
                        <div  style="display: flex; align-items: center; justify-content: center;">
                            <div style="width: 100px; height: 100px;"><label class="total_product">${price_subtotal}</label></div>
                        </div>
                    </td>
                    <td style="width: 50px;"><button type="button" class="btn-close btn-danger delete_product"></button></td>
                </tr>
                `)
            })
            if($("#invoice").is(":checked")){
                $(".invoice_end").show()
                $("#taxes").text(data[0].amount_tax)
                $("#subtotal").text(data[0].amount_untaxed)
                $("#total").text(data[0].amount_total)
            }else{
                $("#taxes").empty()
                $("#subtotal").empty()
                $(".invoice_end").hide()
                $("#total_base").show()
                $("#total").text(data[0].amount_total)
            }
        },

        _onClickDeleteProduct: async function(ev) {
            const tr = $(ev.target).closest('tr');
            const id = tr.find('input').val()
            const id_order = $("#number_order_value").val()
            const products = await ajax.jsonRpc('/budget/delete_line', 'call', {
                "sale_order_id" : parseInt(id_order),
                "line_id" : parseInt(id)
            })
            console.log(products)
            const { status, data } = products;
            const is400 = status === 400;
            if (is400) return
            this._onChangeInvoice(ev)
            tr.remove()
        },

        _onChangeInvoice: async function(ev) {
            if ($("#number_order_value").val() == '') return
            const tax_included = $("#invoice").prop('checked')
            const products = await ajax.jsonRpc('/budget/include_tax', 'call', {
                "sale_id" : parseInt($("#number_order_value").val()),
                "tax_included" : tax_included
            })
            console.log(products)
            const { status, data } = products;
            const is400 = status === 400;
            if (is400) return
            this.build_table_products([data])
        },
        
        _onClickCancel: function(ev) {
            const confirm = "cancel"
            this.Confirm_or_Cancel_Budget(confirm)
        },

        _onClickConfirm: function(ev) {
            const confirm = "confirm"
            this.Confirm_or_Cancel_Budget(confirm)
        },

        Confirm_or_Cancel_Budget: async function(confirm) {
            if ($("#number_order_value").val() == '') return
            const id_order = $("#number_order_value").val()
            const budget = await ajax.jsonRpc('/budget/confirm_or_cancel_order', 'call', {
                "sale_id" : parseInt(id_order),
                "confirm" : confirm
            })
            console.log(budget)
            const { status, data } = budget;
            const is400 = status === 400;
            if (is400) return
            $(".confirm-btn").hide()
            $(".cancel-btn").hide()
            if(confirm == "confirm"){
                var Confirm = _t("Confirmed") 
                const confirmed = '<h2 class="badge bg-success">'+ Confirm +'</h2>'
                $("#status").html(confirmed)
            }else{
                var Confirm = _t("Cancelled") 
                const confirmed = '<h2 class="badge bg-success">'+ Confirm +'</h2>'
                $("#status").html(confirmed)
            }
            $("#invoice").attr("disabled", true)
            $("#openProduct").attr("disabled", true)
            $(".delete_product").hide()
        },

        _onClickDowloadPdf : async function(ev) {
            if($("#number_order_value").val() == '') return
            const sale_id = parseInt($("#number_order_value").val())
            const session_id = this._generateUUID();
            const url = `/my/orders/${sale_id}?access_token=${session_id}&report_type=pdf&download=true`

            const downloadLink = document.createElement('a');
            downloadLink.href = url;
            downloadLink.download = 'myfile.pdf';
            downloadLink.click();

        },

        _generateUUID: function() {
            return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
            const r = (Math.random() * 16) | 0, v = c == "x" ? r : (r & 0x3) | 0x8;
            return v.toString(16);
            });
        },
    })
});

const selectedPartner = (partners, selected_partner) => {
    const copy = [...partners];
    const result = copy.filter(partner => partner.id === selected_partner);
    return result[0]; 
}

const getDirection = (child, addr_type) => {
    const copy = [...child];
    const result = copy.filter(child => child.type === addr_type);
    return result;
}