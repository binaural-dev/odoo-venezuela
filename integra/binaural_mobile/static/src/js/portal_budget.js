/** @odoo-module */

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";
import { Dialog } from "@web/core/dialog/dialog";
import { jsonrpc, RPCError } from "@web/core/network/rpc_service";


// odoo.define('binaural_mobile.portal_budget_form', function(require) {
//     'use strict';

    // const publicWidget = require('web.public.widget');
    // const ajax = require('web.ajax');
    // const { _t } = require('web.core');
    // var Dialog = require('web.Dialog');
    
    const portalBudgetForm = publicWidget.Widget.extend({
        selector: '.o_portal_budget_form',
        events: {
            "keyup #search_text": "_onKeyupSearchText",
            "change #client": "_onChangeClient",
            "change #fee_value": "_onChangeFee",
            "click #search_product": "_onClickSearchProduct",
            "click #exit_products": "_onClickExitProducts",
            "click .delete_product": "_onClickDeleteProduct",
            "click #save_products": "_onClickSaveProducts",
            "change #invoice": "_onChangeInvoice",
            "blur #note": "_onChangeNote",
            "click .cancel-btn": "_onClickCancel",
            "click .confirm-btn": "_onClickConfirm",
            "click #dowload_pdf": "_onClickDowloadPdf",
            "change #same_address": "_onChangeSameAddress",
            "change #qtyProduct": "_onChangeProductQty",
            "click #qtyProduct": "_onClickProductQty",
            "click #openCreateAddressContact": "_onClickCreateDeliveryContact",
            "click #openClient": "_onClickCreateClient",
            "click #registerClient": "_onClickRegisterClient",
            "change #identification": "_onChangeVatPrefix",
            "change #countryClient": "_onChangeCountry",
            "change #stateClient": "_onChangeState",
            "change #municipalityClient": "_onChangeMunicipality",
            "click #openProduct": "_onClickOpenProduct",
            "change .input_qty_line": "_onChangeQtyOrderLine",
        },
        init: function(parent, options) {
            this._super.apply(this, arguments);
            this.order = null;
            this.settings = {};

            this.partners = [];
            this.preLines = [];
            this.products = []; // preLineProducts

            this.limit = 15;
            this.offsetTimes = 0;
        },
        start: async function() {
            const self = this;

            await this._loadSettings();

            $('#client').select2({
                maximumInputLength: 35,
                minimumInputLength: 0,
                maximumSelectionSize: 1,
                allowClear: true,
                ajax: {
                    url: '/budget/client',
                    dataType: 'json',
                    data:  term => ({query: term}),
                    results: (data) => {
                        const { status, data: dt } = data;
                        if (status === 404 || !dt) return {}; 
                        
                        const ret = [];
                        dt.forEach(client => { 
                            const { id: clientId } = client;
                            const isExistclient = ret.find(client => client.id === clientId);
            
                            if (isExistclient) return;
            
                            ret.push({
                                id: client.id,
                                text: client.display_name,
                                isNew: false,
                            });
                            self.partners.push(client); 
                        });
            
                        return { results: ret };
                    }
                    
                },
            });

            ['#numberPhone', '#nameClient',  '#emailClient', "#identification", "#streetDirection"].forEach(function (id) {
                $(id).on('paste', function (e) {
                    e.preventDefault();
                });
            });

            $("#emailClient").attr('maxlength', '50');
            $("#emailClient").keypress(function (e) {
                var regex = new RegExp("^[a-zA-Z0-9@._-]+$");
                var str = String.fromCharCode(!e.charCode ? e.which : e.charCode);
                if (regex.test(str)) {
                    return true;
                }
                e.preventDefault();
                return false;
            });

            $('#identification').attr('maxlength', '9');
            $('#identification').keypress(function (e) {
                var regex = new RegExp("^[0-9]+$");
                var str = String.fromCharCode(!e.charCode ? e.which : e.charCode);
                if (regex.test(str)) {
                    return true;
                }
                e.preventDefault();
                return false;
            });

            $('#nameClient').attr('maxlength', '50');
            $('#nameClient').keypress(function (e) {
                var regex = new RegExp("^[a-zA-Z'áéíóúÁÉÍÓÚ ]+$");
                var str = String.fromCharCode(!e.charCode ? e.which : e.charCode);
                if (regex.test(str)) {
                    return true;
                }
                e.preventDefault();
                return false;
            });

            ['#numberPhone'].forEach(function (id) {
                $(id).attr('maxlength', '18');
                $(id).keypress(function (e) {
                    var regex = new RegExp("^[0-9\-\+]+$");
                    var str = String.fromCharCode(!e.charCode ? e.which : e.charCode);
                    if (regex.test(str)) {
                        return true;
                    }
                    e.preventDefault();
                    return false;
                });
            });

            $(document).on('input', '.qty_product', function() {
                var valor = $(this).val();
                if (isNaN(valor)) {
                    $(this).val(valor.slice(0, -1));
                }
            });

            this._onChangeSameAddress(true)

            if($("#client").val() == "") {
                $("#openProduct").attr("disabled",true)
            }

            this.loadOrder();

            this._onProductModalScroll(self);

        },

        // get
        _getProductById: function (id) {
            id = Number(id);
            return this.products.find(pr => pr.id === id)
        },

        _getDefaultUnitPackage: function (packages, isPackaged) {

            if (packages.length === 0 || !isPackaged) {
                return 1
            }

            return packages[0].qty;
        },

        _getQtyCaseMap: function (product, qtyReq) {
            qtyReq = Number(qtyReq);

            const { allow_out_of_stock_order } = this.settings;

            const { qtyAvailable, isPackaged, packages } = product;
            const qtyFactor = this._getDefaultUnitPackage(packages, isPackaged);

            const qtyCasesMap = {
                qtyReqIsCero: false,
                qtyReqGreaterThanAvailable: false,
                qtyAvailableLowerThanFactor: false,
                qtyReqNotMeetFactor: false,
            }

            const validateQtyFactor = isPackaged;
            const forbidOutOfStockOrder = !allow_out_of_stock_order;

            if (qtyAvailable < qtyFactor && qtyReq === qtyAvailable && forbidOutOfStockOrder) {
                return qtyCasesMap;
            }

            if (validateQtyFactor && qtyAvailable < qtyFactor && forbidOutOfStockOrder) {
                qtyCasesMap.qtyAvailableLowerThanFactor = true;
                return qtyCasesMap;
            }

            if (qtyReq > qtyAvailable && forbidOutOfStockOrder) {
                qtyCasesMap.qtyReqGreaterThanAvailable = true;
                return qtyCasesMap;
            }

            if (validateQtyFactor && qtyReq % qtyFactor != 0) {
                qtyCasesMap.qtyReqNotMeetFactor = true;
                return qtyCasesMap;
            }

            if (qtyReq === 0) {
                qtyCasesMap.qtyReqIsCero = true;

                return qtyCasesMap;
            }

            return qtyCasesMap;
        },

        _getQtyWarning: function (product, qtyRequested) {
            const {
                qtyReqGreaterThanAvailable,
                qtyAvailableLowerThanFactor,
                qtyReqNotMeetFactor
            } = this._getQtyCaseMap(product, qtyRequested);

            const {packages, isPackaged} = product;

            const qtyFactor = this._getDefaultUnitPackage(packages, isPackaged);

            if (qtyReqGreaterThanAvailable) {
                return "La cantidad solicitada es mayor que la cantidad disponible";
            }

            if (qtyAvailableLowerThanFactor) {
                return `La cantidad disponible es menor al múltiplo de ${qtyFactor}`;

            }

            if (qtyReqNotMeetFactor) {
                return `La cantidad solicitada no es un múltiplo de ${qtyFactor}`;
            }

            return;
        },

        _getQtyRequested: function (product, qtyReq) {
            qtyReq = Number(qtyReq);

            const {qtyAvailable, packages, isPackaged} = product;
            const qtyFactor = this._getDefaultUnitPackage(packages, isPackaged);

            const {
                qtyReqGreaterThanAvailable,
                qtyAvailableLowerThanFactor,
                qtyReqNotMeetFactor
            } = this._getQtyCaseMap(product, qtyReq);

            if (qtyReqGreaterThanAvailable) {
                return qtyAvailable;
            }

            if (qtyAvailableLowerThanFactor) {
                return 0;
            }

            if (qtyReqNotMeetFactor) {
								const qtyReqCloserFactor = Math.trunc(qtyReq / qtyFactor) * qtyFactor
								const minimumFactorPack = qtyAvailable > qtyReqCloserFactor ? qtyReqCloserFactor : qtyAvailable;
								return minimumFactorPack;
            }

            return qtyReq;
        },

        _getPreLineByProductId: function (productId) {
            productId = Number(productId)
            const preLine = this.preLines.find(pLine => pLine.productId === productId)

            return preLine
        },

        _getNewPrelineFormat: function (product, qtyRequested) {
            const { id, listPrice } = product;

            const qtyReq = this._getQtyRequested(product, qtyRequested);

            const preLine = {
                productId: id,
                qtyReq,
                priceUnit: listPrice,
            }

            return preLine;
        },

        _getOrderLineFromServiceResp: function (linesResp) {
            const lines = linesResp.map(lineResp => {
                const 
                {
                    id,
                    name,
                    product_template_id,
                    product_uom_qty,
                    price_unit,
                    price_unit_with_tax,
                    price_total,
                    tax_id,
                    price_subtotal,
                    product_id,
                    qty_available,
                    packaging_ids,
                    uom,
                    packaged_product
                } = lineResp;

                const packages = this._getPackagesFormatedFromResp(packaging_ids);

                const line = {
                    id,
                    name,
                    uom,
                    packages,
                    isProductPackaged: packaged_product,
                    productUomQty: product_uom_qty,
                    priceUnit: price_unit,
                    priceUnitWithTax: price_unit_with_tax,
                    priceTotal: price_total,
                    qtyAvailable: qty_available,
                    priceSubtotal: price_subtotal,
                    productTemplate: {
                        id: product_template_id[0],
                        name: product_template_id[1],
                    },
                    tax: {
                        id: tax_id[0],
                        description: tax_id[1],
                        amount: tax_id[2],
                    },
                    product: {
                        id: product_id[0],
                        name: product_id[1],
                    },
                };

                return line;
            })

            return lines;
        },

        _getOrderFormatFromServiceResp: function (orderResp) {
            const 
            {
                id,
                name,
                amount_tax,
                amount_untaxed,
                amount_total,
                state,
                validity_date,
                date_order,
                order_line,
                // partner_id,
                // partner_invoice_id,
                // partner_shipping_id,
                // pricelist_id,
                // payment_term_id,
                // note,
                // tax_included,
            } = orderResp;

            const lines= this._getOrderLineFromServiceResp(order_line);

            const newOrder = {
                id,
                name,
                state,
                amountTax: amount_tax,
                amountUntaxed: amount_untaxed,
                amountTotal: amount_total,
                validityDate: validity_date,
                dateOrder: date_order,
                lines,
                // note,
                // partner: partner_id,
                // partnerInvoice: partner_invoice_id,
                // partnerShipping: partner_shipping_id,
                // pricelist: pricelist_id,
                // paymentTerm: payment_term_id,
                // taxIncluded: tax_included,
            };

            this.order = newOrder;

            return newOrder;
        },

        _getFormatOrderLineRespFromPreLines: function () {

            const orderLines = this.preLines.map(({productId, qtyReq, priceUnit}) => ({
                product_id: productId,
                product_uom_qty: qtyReq,
                price_unit: priceUnit,
            }))

            return orderLines;
        },

        _getNewOrder: function (order_line) {
            const address = $("#same_address").is(':checked') ? parseInt($("#billing_address").val()) : parseInt($("#project").val());

            const order = {
                partner_id: +$("#client").val(),
                partner_invoice_id: +$("#billing_address").val(),
                partner_shipping_id: address,
                pricelist_id: +$("#fee_value").val(),
                payment_term_id: +$("#payment_terms_value").val(),
                order_line,
                note: $("#note").val(),
                tax_included: $("#invoice").is(':checked')
            }

            return order;
        },

        _getClients: async () => {
            const clients = $.ajax({
                type: "GET",
                dataType: 'json',
                url: '/budget/client',
                contentType: "application/json; charset=utf-8",
                data: JSON.stringify({'query': ""}),
            });

            return clients;

        },

        _getPackagesFormatedFromResp: function (packagesResp) {
            const packages = packagesResp.map(packResp => {

                const {
                    id,
                    name,
                    qty,
                    product_uom_id,
                    sales,
                    purchase
                } = packResp;

                return {
                    id,
                    name,
                    qty,
                    productUomId: {
                        id: product_uom_id[0],
                        name: product_uom_id[1],
                    },
                    sales,
                    purchase
                };
            })

            return packages;
        },

        _getProductFormatedFromResp: function (productResp) {
            const 
            {
                id,
                name,
                type,
                display_name,
                qty_available,
                quantity,
                list_price,
                default_code,
                barcode,
                brand_id,
                taxes_id,
                packaged_product,
                uom_id,
                product_template_attribute_value_ids,
                msg_price,
                image,
                packaging_ids
            } = productResp;

            const packages = this._getPackagesFormatedFromResp(packaging_ids);

            return {
                id,
                name,
                type,
                quantity, // In integra app this quantity field is used as qtyAvailable
                barcode,
                image,
                packages,
                displayName: display_name,
                qtyAvailable: quantity,
                listPrice: list_price,
                defaultCode: default_code,
                brand: {
                    id: brand_id[0],
                    name: brand_id[1],
                },
                taxesId: taxes_id,
                isPackaged: packaged_product,
                uom: {
                    id: uom_id[0],
                    name: uom_id[1],
                },
                productTemplateAttributeValueIds: product_template_attribute_value_ids,
                msgPrice: msg_price,
            }
        },

        _getProductsFormatedFromResp: function (productResp) {
            const products = productResp.map( prResp => {
                return this._getProductFormatedFromResp(prResp);
            });

            return products;
        },

        _getProducts: async (self, productCode = '') => {
            let domain = {
                "fee": +$("#fee_value").val(),
                "limit": self.limit,
                "offset": self.limit * self.offsetTimes,
            }

            if (productCode !== '') {
                domain['product'] = productCode;
            }

            const products = await jsonrpc('/budget/product', domain);

            const resp = JSON.parse(products);

            if (!resp.data) return resp;
            
            const productsToAdd = self._getProductsFormatedFromResp(resp.data);

            self.products.push(...productsToAdd);

            return resp;
        },

        _generateUUID: function() {
            return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
            const r = (Math.random() * 16) | 0, v = c == "x" ? r : (r & 0x3) | 0x8;
            return v.toString(16);
            });
        },

        // set
        _setResetProductLoad: function () {
            this.offsetTimes = 0;
            this.products = [];
        },

        _setResetPrelines: function  () {
            this.preLines = [];
        },

        _setNewPreline: function (preLine) {
            this.preLines.push(preLine);
            return preLine;
        },

        _setEditPreline: function (preLine) {

            this.preLines = this.preLines.map(pLine => {
                if (pLine.productId !== preLine.productId) return pLine;

                return {
                    ...pLine,
                    ...preLine,
                };
            })

            return preLine;

        },

        _setRemovePrelineByProductId: function (productId) {
            productId = Number(productId);
            this.preLines = this.preLines.filter(preLine => preLine.productId !== productId);
            return;
        },

        _setPreline: function (product, qtyReq) {
            qtyReq = Number(qtyReq)

            const { id } = product;

            const existPreline = this._getPreLineByProductId(id);

            const preLine = this._getNewPrelineFormat(product, qtyReq);

            if (!preLine.qtyReq) {
                return this._setRemovePrelineByProductId(id);
            }

            if (existPreline) {
                return this._setEditPreline(preLine);
            }

            return this._setNewPreline(preLine);

        },

        _setOrderFromServiceResp: function (orderResp) {
            this.order = this._getOrderFormatFromServiceResp(orderResp);
        },

        // load

        _loadSettings: async function () {
            try {
                let a = true
                const settings = await jsonrpc('/settings/read', {a:a})
                this.settings = settings;
            } catch (error) {
                if (error instanceof RPCError) {
                    alert(error.data.message);
                } else {
                    return Promise.reject(error);
                }
            }
        },

        SearchFilterInputs : async function (data, tag){
            let ver = await $.ajax({
                url: "/budget/search_filter",
                type: "GET",
                data: data,
            });
            this.onSuccessCallBack(ver, tag)
        },

        loadOrder: async function(buildTax = false) {
            const order = await jsonrpc('/budget/order/read', {
                "sale_id" : parseInt($("#number_order_value").val()),
            })
            const { status, data } = order;
            const is409 = status === 409;
            if (is409) return

            const orderResp = data;

            this._setOrderFromServiceResp(orderResp);

            this.build_table_products([data],buildTax)
        },

        includeTax: async function(){
            if ($("#number_order_value").val() == '') return
            const tax_included = $("#invoice").prop('checked')
            const note = $("#note").val()
            const products = await jsonrpc('/budget/include_tax', {
                "sale_id" : parseInt($("#number_order_value").val()),
                "tax_included" : tax_included,
                "note": note
            })
            const { status, data } = products;
            const is409 = status === 409;
            if (is409) return
            // this.build_table_products([data],false)
        },

        _createOrder: async function (orders) {
            if($("#number_order_value").val()) return;
            const products = await jsonrpc('/budget/order/create',
                {"order" :orders.void}
            )
            const { status, data, msg} = products;
            const is400e = status === 400;

            if (is400e) {
                throw msg;
            }

            $("#note").val("")
            $("#product_head").show()
            $("#number").show()
            $("#number_order").text(data[0].name)
            $("#number_order_value").val(data[0].id)
            $("#same_address").attr('disabled', true)
            $("#invoice").attr('disabled', false)

            await this.loadOrder()

        },

        _updateOrder: async function (orders) {

            if(orders.withValues.length === 0) return;

            orders.withValues.forEach(line => {
                line.sale_order_id.id = +$("#number_order_value").val()
            })

            const products = await jsonrpc('/budget/create/order/line',
                {"sale_orders": orders.withValues}
            )
            const { status:st, data:dt, msg } = products;

            const is400 = st === 400;

            if (is400) {
                $("#save_products").attr('disabled', false)
                throw msg;
            }

            // this.order = dt[0]

            await this.loadOrder()

        },

        _loadContacts: async function () {
            const {data, status } = await this._getClients()

            const is400e = status === 400;

            if (is400e) return 

            this.partners = data;

            this._loadContactSelectOptions(this.partners, $('#client').val());
        },

        _loadContactSelectOptions: (partners, value) => {
            const $addressSelections = $("select.address_selection");
            const labelFee = $("#fee")
            const labelPayTerms = $("#payment_terms")

            if (!Boolean(value)) return

            const client = selectedPartner(partners, parseInt(value));
            const { property_product_pricelist, property_payment_term_id } = client;

            $.each($addressSelections, (index, addressSelection) => {
                const $selection = $(addressSelection);
                const addr_type = $selection.data("address");
                const partner_child = getDirection([ ...client.child_ids ], addr_type);
                $selection.empty();
                if(partner_child.length == 0){
                    $selection.append(`<option value="${client.id}">${client.street || "No Aplica"}</option>`);
                }else{
                    if(client.street){
                        $selection.append(`<option value="${client.id}">${client.street}</option>`);
                    }

                    partner_child.forEach((el) => {
                        $selection.append(`<option value="${el.id}">${el.street || "No Aplica"}</option>`);
                    })
                }
            });
            
            labelFee.text(property_product_pricelist.length > 0 ? property_product_pricelist[1] : "")
            $("#fee_value option:first-child[value='']").remove();
            $("#fee_value").val(property_product_pricelist.length > 0 ? property_product_pricelist[0] : "")
            labelPayTerms.text(property_payment_term_id.length > 0 ? property_payment_term_id[1] : "").val(property_payment_term_id.length > 0 ? property_payment_term_id[0] : "");
            $("#payment_terms_value").val(property_payment_term_id.length > 0 ? property_payment_term_id[0] : "")
            $("#plus_code_label").text(client.plus_code.length > 0 ? client.plus_code : "")
            $('#plus_code_label').attr('href', client.plus_code.length > 0 ? client.plus_code : "");

            
            $("#openProduct").attr('disabled', false)
            $("#same_address").attr('disabled', false)

            if (Boolean($("#client").val())) {
                $("#openCreateAddressContact").attr('disabled', false)
                $("#openCreateAddressContact").removeClass('d-none')
            }
            else {
                $("#openCreateAddressContact").attr('disabled', true)
                $("#openCreateAddressContact").addClass('d-none')
            }
        },

        // render
        buildTableTax: function(){
            let taxProducts = {};
            const symbol = $("#symbolB").val()
            let symbolAfter = ""
            let symbolBefore = ""
            let decimalPlaces = +$("#decimal").val()
            
            if($("#positionS").val() == "after"){
                symbolAfter = symbol
            }else{
                symbolBefore = symbol
            }

            $('#product_list tr').each(function() {
                let valueIva = $(this).find('#value_iva').val();
                let totalProduct = parseFloat($(this).find('#value-total-product').val())
                if (taxProducts[valueIva]) {
                    taxProducts[valueIva][0] = parseFloat(taxProducts[valueIva][0]) + (totalProduct / 100 * valueIva)
                    taxProducts[valueIva][0] = taxProducts[valueIva][0].toFixed(decimalPlaces)
                    taxProducts[valueIva][1] = (parseFloat(taxProducts[valueIva][1]) + totalProduct).toFixed(decimalPlaces) 
                } else {
                    if(valueIva == 0) {
                        let total = (0).toFixed(decimalPlaces)
                        taxProducts[valueIva] = [total,totalProduct]
                        return
                    }
                let total = parseFloat((totalProduct / 100 * valueIva)).toFixed(decimalPlaces)
                taxProducts[valueIva] = [total,totalProduct]
                }
            });

            let taxLabel = ``
            for (let key in taxProducts) {
                let valTax = 0
                let valTotal = 0
                valTax = key == 0 ? valTax.toFixed(decimalPlaces) : taxProducts[key][0];
                valTotal = parseFloat(taxProducts[key][1]).toFixed(decimalPlaces)
                if(key == 0){
                    taxLabel += `<div class="d-flex justify-content-end iva-remove">
                                        <label class="form-label" style="font-weight: bolder; padding-right:3px;">BI Exento: </label>
                                        <label > ${symbolBefore} ${valTotal} ${symbolAfter}</label>
                                    </div>`
                }else{
                    taxLabel += `<div class="d-flex justify-content-end iva-remove">
                                        <label class="form-label" style="font-weight: bolder; padding-right:3px;">BI G IVA ${key}%: </label>
                                        <label > ${symbolBefore} ${valTotal} ${symbolAfter}</label>
                                    </div>`
                    taxLabel += `<div class="d-flex justify-content-end iva-remove">
                        <label class="form-label" style="font-weight: bolder; padding-right:3px;">IVA ${key}%: </label>
                        <label > ${symbolBefore} ${valTax} ${symbolAfter}</label>
                    </div>`
                }
            }
            $('#taxes-invoices-budget').html(taxLabel)
        },

        confirm_or_Cancel_Budget: async function(confirm) {
            if ($("#number_order_value").val() == '') return
            const id_order = $("#number_order_value").val()
            const budget = await jsonrpc('/budget/confirm_or_cancel_order', {
                "sale_id" : parseInt(id_order),
                "confirm" : confirm
            })
            const { status, data, msg} = budget;
            const is400 = status === 400;
            if (is400) {
                $("#error_msg").text(msg)
                $("#error_confirm_cancel").modal('show')
                return
            }
            $(".confirm-btn").hide()
            $(".cancel-btn").hide()
            if(confirm == "confirm"){
                var Confirm = _t("Confirmado") 
                const confirmed = '<h2 class="badge bg-success">'+ Confirm +'</h2>'
                $("#status").html(confirmed)
            }else{
                var Confirm = _t("Cancelado") 
                const confirmed = '<h2 class="badge bg-danger">'+ Confirm +'</h2>'
                $("#status").html(confirmed)
            }
            $(".cancel_confirmed_input").remove()
            $(".delete_product").remove()
            $("#openClient").remove()
            $("#client").select2("enable", false)

            await this.loadOrder()
        },

        _msgErrorRegisterClient: function(msg){
            $("#labelMsg").text(msg)
            $("#errorMsg").modal('show')
            setTimeout(function () {
                $("#errorMsg").modal('hide')
            }, 2500);
        },

        _appendProduct: async (self, products, allow_out_of_stock_order,stock_packaging, tbody) => {

            if (!products) return;

            // tbody.empty()
            let priceLabel = _t("Precio")
            let qtyLabel = _t("Cant.")
            const symbol = $("#symbolB").val()
            let symbolAfter = ""
            let symbolBefore = ""
            let decimalPlaces = +$("#decimal").val()

            if($("#positionS").val() == "after"){
                symbolAfter = symbol
            }else{
                symbolBefore = symbol
            }

            let dont_show_quantity_available = false
            try{
                dont_show_quantity_available = await self._rpc(
                    {
                    "model": "res.users",
                    "method":"has_group",
                    "args": ['binaural_mobile.group_sellers_show_quantity_available']
                    }
                )
            }catch(e){}

            products.forEach(product => {
                let { display_name, list_price, image, quantity, id, msg_price, uom_id, type, packaged_product, packaging_ids } = product
                let displayQtyOrType = ""
                let packFactorLabel = ""

                const hasPackageFactorValid = stock_packaging && packaging_ids.length > 0 && packaged_product;

                if(!dont_show_quantity_available){
                    if(quantity == 0 && !allow_out_of_stock_order && type != "product") {
                        displayQtyOrType = type
                    }else{
                        displayQtyOrType = quantity.toFixed(2) + ' ' + uom_id[1]
                    }
                }

                if(hasPackageFactorValid) {
                    const packagingQty = self._getDefaultUnitPackage(packaging_ids, packaged_product);
                    packFactorLabel = `<label class="form-text" style="min-width: max-content;">Solo múltiplos de ${packagingQty}</label><input type='hidden' id='product_qty_pack' value='${packagingQty}'/><br/>`;
                }

                if(type != "product"){
                    quantity = 999
                }

                list_price = list_price.toFixed(decimalPlaces)
                tbody.append(`
                    <tr class="productItem" data-id="${id}" id="productItem${id}">
                        <td class="text-center"><img style="width: auto; height:70px;" src="${image}"/></td>
                        <td colspan="2">
                            <label style="font-weight: bolder; font-size: 15px;" class="name_product">${display_name}</label><br/>
                            <input type="hidden" class="val_product" value="${id}"/>
                            <label class="form-text">${priceLabel}:</label>
                            <label class="form-text price_product" style="font-weight: bolder;">${symbolBefore} ${list_price} ${symbolAfter}</label><br/>
                            <label class="form-text" style="font-weight: bolder;">${displayQtyOrType || ""}</label><input type='hidden' id="qtyAvailable" value='${quantity}'/>
                        </td>
                        <td style="width: 150px;">
                            <input type="text" class="form-control qty_product" id='qtyProduct' data-qty-available="${quantity}" placeholder="${qtyLabel}"/>
                            ${packFactorLabel}
                            <label class="form-text text-success">${msg_price || ''}</label>
                        </td>
                    </tr>
                `)
            });

        },

        _renderNotFoundProducts: (self, tbody, productCode) => {
            const isNoContent = self.products.length == 0;

            if (!isNoContent) {

                const existNotFoundEl = $('#table_inside #productsNotFound').length ? true : false;

                if (existNotFoundEl) {
                    tbody.empty();
                }

                return false;
            };

            var noFound = _t("No se encontraron productos con el código o nombre:")

            tbody.empty()

            tbody.append(`
                <div class="alert alert-primary" style="font-weight: bolder;" role="alert" id="productsNotFound">
                    ${noFound} ${productCode}
                </div>
            `)

            $('#save_products').attr('disabled', true)

            return true;

        },

        _renderProducts: async (self, reset = false, productCode = '') => {
            const resp = await self._getProducts(self, productCode);
            const { data: products, stock_packaging, allow_out_of_stock_order } = resp;
            const tbody = $("#table_inside");

            if (reset) {
                tbody.empty();
            }

            if (self._renderNotFoundProducts(self, tbody, productCode)) return;

            self._appendProduct(self, products, allow_out_of_stock_order, stock_packaging, tbody)
        },

        _showQtyWarning: function (product, qtyRequested) {
            const warning = this._getQtyWarning(product, qtyRequested);

            if (!warning) return;

            this.showError(warning);
        },

        showError: function( msg = "Verifica las unidades del producto"){
            $("#errorQty").modal('show')
            $("#errorQtyMsg").html(msg);
            setTimeout(function () {
                $("#errorQty").modal('hide')
            }, 4000);
        },

        validateInputEmpty:function(){
            const querySelector = document.querySelectorAll("#table_inside input.qty_product")
            let counter = 0
            querySelector.forEach(input => {
                if (input.value.trim() != ''){ 
                    counter++
                }
            })
            if (counter > 0){
                $('#save_products').attr('disabled', false)
            }else{
                $('#save_products').attr('disabled', true)
            }
        },
        
        _update_order_line: async function(order_line) {
            const params = order_line;

            const settings = {
                type: "post"
            }

            const resp = await jsonrpc(
                '/budget/order/line/edit', 
               
                params,
                settings
            )

            const { status, msg } = resp;

            if (status === 400) {
                throw msg;
            } 

            return resp;

        },

        _getRenderQtyOrderLine: function (order, line) {
            const { productUomQty, qtyAvailable, packages, uom, isProductPackaged } = line;
            const { state } = order;
            const showInput = state === 'draft';
            
            const packageQty = this._getDefaultUnitPackage(packages, isProductPackaged);
            const packagingQtyElem = packageQty > 1 ? `<label class="form-text" style="padding-right:3px;">Múltiplos de ${packageQty} </label>`: '';

            const isPackaged = isProductPackaged ? 1 : 0;

            const uomElem = uom ? ` <label class="form-text" style="padding-right:3px;">${uom}</label>` : '';

            const elem = `
                <div class="form-group">
                    <label class="form-text" style="padding-right:3px;">Cantidad: </label>
                    <label>
                        <input 
                            type="text"
                            style="width: 60px; font-size: 15px;"
                            class="form-control p-1 input_qty_line" 
                            value="${productUomQty.toFixed(2)}"
                            data-qty-available="${qtyAvailable}"
                            data-qty-pack="${packageQty}"
                            data-is-packaged="${isPackaged}"
                        />
                    </label>
                    ${uomElem}
                    <br/>
                    ${packagingQtyElem}
                </div>
            `;

            if (showInput) return elem;

            // state == draft -> show input to type qty
            return `
                <div class="form-group">
                    <label class="form-text" style="padding-right:3px;">
                        Cantidad: ${productUomQty.toFixed(2)}
                    </label>
                    ${uomElem}
                    <br/>
                    ${packagingQtyElem}
                </div>
            `;
        },

        build_table_products: async function(data,buildTax) {

            if(buildTax && $("#invoice").is(":checked")){
                await this.loadOrder()
                return
            }
            const tbody = $("#product_list")
            const order = this.order;
            const { amountUntaxed, amountTotal, lines, state } = order;

            tbody.empty();

            var unitLabel = _t("Precio Unitario: ")
            const symbol = $("#symbolB").val()
            let symbolAfter = ""
            let symbolBefore = ""
            let decimalPlaces = +$("#decimal").val()
            const allow_out_of_stock_order = this.settings.allow_out_of_stock_order;

            if($("#positionS").val() == "after"){
                symbolAfter = symbol
            }else{
                symbolBefore = symbol
            }

            lines.forEach(line => {
                let { id, tax, name, productUomQty, priceUnit, priceSubtotal, qtyAvailable } = line
                priceUnit = priceUnit.toFixed(decimalPlaces) 
                priceSubtotal = priceSubtotal.toFixed(decimalPlaces)
                let taxLabel = ''
                let taxValue = 0
                let msgDeleteProduct = ``
                if($("#invoice").is(":checked")){
                    taxLabel = tax.description || "Exento";
                    taxValue = tax.amount
                }
                if(productUomQty > qtyAvailable && !allow_out_of_stock_order){
                    msgDeleteProduct = `<label class='alert-danger form-text'>Verifique cantidad disponible de productos</label><br/>`
                }
                let trash = state === "draft" ? `<button type="button" class="fa fa-trash-o delete_product cancel_confirmed_input" 
                            style="background-color: transparent;border: none;padding: 0; color:red;"></button>` : "";

                const qtyOrderLineElem = this._getRenderQtyOrderLine(order, line)

                if($("#status-val").val() == 'cancel' || $("#status-val").val() == 'sale') trash = ``
                tbody.append(`
                <tr data-id="${id}">
                    <td colspan="4" style="font-size: 15px;">
                        <label style="font-weight: bolder;">${name}</label> <input type="hidden" value="${id}"> <br/>
                        ${qtyOrderLineElem}
                        ${msgDeleteProduct}
                        <label class="form-text" style="padding-right:3px;">${unitLabel}</label><label class="form-text" style="font-weight: bolder;">${symbolBefore} ${priceUnit} ${symbolAfter}</label><br/>
                    </td>
                    <td class="text-center" style="font-size: 15px;">
                        <div style="display: flex; align-items: center; justify-content: center;float:right;">
                            <div style="width: 100px; height: 50px;">
                                <label class="total_product">${symbolBefore} ${priceSubtotal} ${symbolAfter}</label>
                                <input type="hidden" id="value-total-product" value="${priceSubtotal}"/>
                            </div>
                        </div>
                        <div>
                            <label class="badge bg-primary" id="tax-product">${taxLabel}</label>
                            <input type="hidden" id="value_iva" value="${taxValue}"/>
                        </div>
                    </td>
                    <td style="width: 50px;">
                        ${trash}
                    </td>
                </tr>
                `)
            })
            if($("#invoice").is(":checked")){
                $(".invoice_end").show()
                $("#subtotal").text(amountUntaxed.toFixed(decimalPlaces))
                $("#total").text(amountTotal.toFixed(decimalPlaces))
                this.buildTableTax()
            }else{
                $("#subtotal").empty()
                $(".invoice_end").hide()
                $("#total_base").show()
                $(".iva-remove").remove()
                $(".total").show()
                $("#total").text(amountTotal.toFixed(decimalPlaces))
            }
        },

        _check_order_line_qty_quantity: async function (ev) {
            const inputElem = ev.target;
            const qty = +inputElem.value;
            const qtyAvailable = +inputElem.dataset.qtyAvailable;
            const qtyPack = Number(inputElem.dataset.qtyPack);
            const validateQtyFactor = Boolean(Number(inputElem.dataset.isPackaged));
            const forbidOutOfStockOrder = !this.settings.allow_out_of_stock_order;

            if (qtyAvailable < qtyPack && qty === qtyAvailable && forbidOutOfStockOrder) {
                return true;
            }

            if (qtyAvailable < qtyPack && forbidOutOfStockOrder && validateQtyFactor){
                this.validateInputEmpty()
                throw `La cantidad disponible es menor al múltiplo de ${qtyPack}`;
            }

            if (qty > qtyAvailable && forbidOutOfStockOrder) {
                ev.target.value = qtyAvailable
                throw "La cantidad es mayor que la cantidad disponible";
            }

            if(qty % qtyPack != 0 && validateQtyFactor){
                ev.target.value = inputElem.defaultValue;
                throw `La cantidad no es un múltiplo de ${qtyPack}`;
            }

            this.validateInputEmpty()

            return true;
        },

        // Events
        _onChangeQtyOrderLine: async function(ev) {
            try {
                const tr = $(ev.target).closest('tr');

                if (!tr.length) return;

                await this._check_order_line_qty_quantity(ev)

                const line_id = +tr[0].dataset.id;
                const qty = +ev.target.value

                const data = {
                    line_id,
                    product_uom_qty: qty
                }

                await this._update_order_line(data)

                await this.loadOrder()

            } catch (error) {
                this.showError(error)
            }
        },

        _onClickSearchProduct: async function(ev) {
            if($('#search_text').val() != ''){
                const self = this;
                const productCode = $('#search_text').val()
                
                $('#search_product').attr('disabled', true)

                self._setResetProductLoad();

                await this._renderProducts(self, true, productCode);
            }
        },

        _onProductModalScroll: (self) => {
            let scrollContainer = $('#addProduct .modal-body');
            
            if (!scrollContainer.length) return;
            
            scrollContainer = scrollContainer[0]
            
            scrollContainer.addEventListener('scroll', async () => {

                if (
                    scrollContainer.scrollTop + scrollContainer.clientHeight >= 
                    scrollContainer.scrollHeight
                ) {
                    const productCount = self.products.length;

                    self.offsetTimes += 1;

                    const productCode = $('#search_text').val()
                    
                    await self._renderProducts(self, false, productCode)

                    const diffCount = productCount - self.products.length;

                    if (!diffCount) return;

                    const productItem = $('#addProduct .productItem');
            
                    if (!productItem.length) return;
                    
                    const productItemClientHeight = productItem[0].clientHeight;

                    scrollContainer.scrollTop = scrollContainer.scrollTop - (diffCount * productItemClientHeight);

                }
            });
        },

        _onClickExitProducts: function(ev) {
            $("#addProduct").modal('hide')
            $('#save_products').attr('disabled', true)
            $('#search_product').attr('disabled', true)
            $('#search_text').val('')
            $("#table_inside").empty()

            this._setResetPrelines();
            this._setResetProductLoad();
        },

        _onChangeFee: async function(ev){
            if ($("#number_order_value").val() == '') return
            
            const saleOrder = await jsonrpc('/budget/update_pricelist',{
                "budget": $("#number_order_value").val(),
                "fee": $("#fee_value").val(),
            });

            const { status, data } = saleOrder;
            const is400e = status === 400;
            if (is400e) return 

            // this.build_table_products(data,true)
            this.loadOrder(true);
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

        _onClickSaveProducts: async function(ev) {
            $("#save_products").attr('disabled', true)

            let isPassed = false
            const orders = {
                void: null,
                withValues: [],
            };

            const orderLines = this._getFormatOrderLineRespFromPreLines();
            const currentSaleOrderId = $("#number_order_value").val()
            const order = this._getNewOrder(orderLines);

            if(!currentSaleOrderId && !isPassed){
                orders.void = {
                    sale_order: order,
                    tax_included: order.tax_included,
                }

                isPassed = true;
            } else {

                const orderWithValues = {
                    sale_order_id: {
                        id: currentSaleOrderId,
                        ...order
                    }
                }

                orders.withValues.push(orderWithValues);

            }

            try {
                await this._updateOrder(orders);
                await this._createOrder(orders);

                this._onClickExitProducts()
                $("#table_inside").empty();
            } catch (error) {
                this.showError(error)
                // Dialog.alert(this,error, { title: 'Error' });
            }
        },

        _onClickProductQty: function(){
            $('#save_products').attr('disabled', true)
        },

        _onChangeProductQty: async function(ev) {
            const inputElem = $(ev.target);
            const tr = ev.target.closest('tr');
            const productId = $(tr).data("id");
            const modalSaveProductBtnElem = $('#save_products');

            let inputValue = inputElem.val();

            const product = this._getProductById(productId);
            const preLine = this._setPreline(product, inputValue);
            
            this._showQtyWarning(product, inputValue);

            inputValue = '';

            if (preLine) {
                inputValue = preLine.qtyReq;
            }

            inputElem.val(inputValue);

            modalSaveProductBtnElem.attr('disabled', !this.preLines.length);

        },

        _onClickDeleteProduct: async function(ev) {
            const tr = $(ev.target).closest('tr');
            const id = tr.find('input').val()
            const id_order = $("#number_order_value").val()
            const products = await jsonrpc('/budget/delete_line', {
                "sale_order_id" : parseInt(id_order),
                "line_id" : parseInt(id)
            })
            const { status, data , message} = products;
            const is400 = status === 400;
            if (is400) {
                Dialog.alert(this,message, { title: 'Error' });
                return
            }
            this._onChangeInvoice(ev)
            tr.remove()
        },

        _onChangeInvoice: async function(ev) {
            await this.includeTax()
            await this.loadOrder()
        },

        _onChangeNote: async function(ev) {
            await this.loadOrder()
        },

        _onClickCancel: function(ev) {
            const confirm = "cancel"
            this.confirm_or_Cancel_Budget(confirm)
        },

        _onClickConfirm: function(ev) {
            const confirm = "confirm"
            this.confirm_or_Cancel_Budget(confirm)
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

        _onClickRegisterClient: async function(ev){
            if($("#identification").val().trim() && $("#nameClient").val().trim() && 
                $("#streetDirection").val().trim() && $("#prefixClient").val().trim() != ""){
                const registerClient = await jsonrpc('/budget/create_client', {
                    "prefix":$("#prefixClient").val(),
                    "vat": $("#identification").val(),
                    "street": $("#streetDirection").val(),
                    "name": $("#nameClient").val(),
                    "number": $("#numberPhone").val(),
                    "email": $("#emailClient").val(),
                    "country": $("#countryClient").val(),
                    "state": $("#stateClient").val(),
                    "municipality": $("#municipalityClient").val(),
                    "city": $("#cityClient").val(),
                    "parish": $("#parishClient").val(),
                    "type": $("#typeContactCreateClientModal").val(),
                    "parent_id": $("#client").val(),
                    "plus_code": $("#plus_code").val(),
                })
                const { status, msg } = registerClient;
                if (status == 400 || status == 409){
                    this._msgErrorRegisterClient(msg)
                    return
                } 
                $(".register-client").val('')
                $("#createClient").modal('hide')

                this._loadContacts();
                return
            }
            let msgValidate = 'Debes de llenar los campos obligarios del formulario.'
            this._msgErrorRegisterClient(msgValidate)

        },

        _onChangeVatPrefix: async function(ev){
            if($("#identification").val().trim() && $("#prefixClient").val().trim()){
                const prefix = $("#prefixClient").val()
                const vat = $("#identification").val()
                const nameClient = await jsonrpc('/budget/get_name_client', {
                    "prefix":prefix,
                    "vat": vat,
                })
                const { status, data } = nameClient;
                if (status == 400 ) return
                $("#nameClient").val(data)
            }
        },

        _onChangeCountry: function(ev){
            if($("#countryClient")!=""){
                const filter = $("#countryClient").val();
                const model = $("#countryClient").attr("name");
                const tag = "#stateClient";
                const namemodel = "2"
                const data  = {
                    filter,
                    model,
                    target: "state_id",
                    namemodel,
                    field: "name",
                    ref: "country_id",
                }
                this.SearchFilterInputs(data, tag)
            }
        },

        _onChangeState: function(ev){
            if($("#stateClient").val()!=""){
                const filter = $("#stateClient").val();
                const model = $("#stateClient").attr("name");
                const municipalityTag = "#municipalityClient";
                const cityTag = "#cityClient";
                const municipalityNamemodel = "3";
                const cityNamemodel = "5";
                
                const municipalityData = {
                    filter,
                    model,
                    target: "municipality_id",
                    namemodel: municipalityNamemodel,
                    field: "name",
                    ref: "state_id",
                };
                this.SearchFilterInputs(municipalityData, municipalityTag);
                
                const cityData = {
                    filter,
                    model,
                    target: "city_id",
                    namemodel: cityNamemodel,
                    field: "name",
                    ref: "state_id",
                };
                this.SearchFilterInputs(cityData, cityTag);
            }
        },

        _onChangeMunicipality: function(ev){
            if($("#municipalityClient").val()!=""){
                const filter = $("#municipalityClient").val();
                const model = $("#municipalityClient").attr("name");
                const tag = "#parishClient";
                const namemodel = "4"
                const data  = {
                    filter,
                    model,
                    target: "parish_id",
                    namemodel,
                    field: "name",
                    ref: "municipality_id",
                }
                this.SearchFilterInputs(data, tag)
            }
        },

        onSuccessCallBack: function(data, tag){
            $(tag).html(data);
            $(tag).append($("<option></option>").attr("value", '').text('Seleccione'))
            $.each(data, function(key, field ) {
                $(tag).append($("<option></option>").attr("value", field.id).text(field.name));
            });
        },

        _onClickOpenProduct: async function () {
            await this._loadSettings();
            this._setResetProductLoad();
            this._setResetPrelines();
            await this._renderProducts(this, true);
        },

        _onClickCreateDeliveryContact: () => {
            $("#typeContactCreateClientModal").val("delivery")
        },

        _onClickCreateClient: () => {
            $("#typeContactCreateClientModal").val("contact")
        },

        _onChangeClient: async function ({target}) {
            this._loadContactSelectOptions(this.partners, target.value);
            if($("#number_order_value").val()){
                const partner = await jsonrpc('/budget/update_partner',
                    {
                        "budget" :$("#number_order_value").val(),
                        "partner" : $("#client").val(),
                    }
                )
                const { status:st, msg } = partner;
                const is400 = st === 400;
                if (is400) alert(msg)  
            }
        },

    })

    publicWidget.registry.portalBudgetForm = portalBudgetForm

    // return portalBudgetForm;
// });

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
