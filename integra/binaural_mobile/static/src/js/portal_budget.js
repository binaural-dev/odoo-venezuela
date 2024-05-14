odoo.define('binaural_mobile.portal_budget_form', function(require) {
    'use strict';

    const publicWidget = require('web.public.widget');
    const ajax = require('web.ajax');
    const { _t } = require('web.core');
    var Dialog = require('web.Dialog');
    
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
            this.partners = [];
            this.limit = 15;
            this.offsetTimes = 0;
            this.products = []
        },
        start: function() {
            const self = this;

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
                        const { status, data:dt } = data;
                        const is400e = status === 400;
                        if (is400e) return 
                        const ret = [];
                        _.each(dt, function (client) {
                            const { id: clientId } = client
                            const isExistclient = ret.find(client => client.id === clientId);

                            if (isExistclient) return;

                            ret.push({
                                id: client.id,
                                text: client.display_name,
                                isNew: false,
                            });
                            self.partners.push(client); 
                        });

                        return {results: ret};
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

            this.refreshOrderLines()

            this._onProductModalScroll(self);

        },
        _onClickOpenProduct: function () {
            this._renderProducts(this);
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
        _onClickCreateDeliveryContact: () => {
            $("#typeContactCreateClientModal").val("delivery")
        },
        _onClickCreateClient: () => {
            $("#typeContactCreateClientModal").val("contact")
        },
        _onChangeClient: async function ({target}) {
            this._loadContactSelectOptions(this.partners, target.value);
            if($("#number_order_value").val()){
                const partner = await ajax.jsonRpc('/budget/update_partner', 'call',
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
                  $selection.append(`<option value="${client.id}">${client.street || "No Apply"}</option>`);
                }else{
                  partner_child.forEach((el) => {
                      $selection.append(`<option value="${el.id}">${el.street || "No Apply"}</option>`);
                  })
                }
            });
            
            labelFee.text(property_product_pricelist.length > 0 ? property_product_pricelist[1] : "")
            $("#fee_value option:first-child[value='']").remove();
            $("#fee_value").val(property_product_pricelist.length > 0 ? property_product_pricelist[0] : "")
            labelPayTerms.text(property_payment_term_id.length > 0 ? property_payment_term_id[1] : "").val(property_payment_term_id.length > 0 ? property_payment_term_id[0] : "");
            $("#payment_terms_value").val(property_payment_term_id.length > 0 ? property_payment_term_id[0] : "")
            
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

        _onChangeFee: async function(ev){
            if ($("#number_order_value").val() == '') return
            
            const saleOrder = await ajax.jsonRpc('/budget/update_pricelist', 'call',{
                "budget": $("#number_order_value").val(),
                "fee": $("#fee_value").val(),
            });

            const { status, data } = saleOrder;
            const is400e = status === 400;
            if (is400e) return 

            this.build_table_products(data,true)
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

        _appendProduct: async (self, products, allow_out_of_stock_order,stock_packaging, tbody) => {

            if (!products) return;

            // tbody.empty()
            let priceLabel = _t("Precio")
            let qtyLabel = _t("Cant.")
            let multiplesLabel = ``
            const symbol = $("#symbolB").val()
            let symbolAfter = ""
            let symbolBefore = ""
            let decimalPlaces = +$("#decimal").val()          

            if($("#positionS").val() == "after"){
                symbolAfter = symbol
            }else{
                symbolBefore = symbol
            }

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
                let { display_name, list_price, image, quantity, id, msg_price, uom_id, type, packaged_product } = product
                let displayQtyOrType = ""

                if(!dont_show_quantity_available){
                  if(quantity == 0 && !allow_out_of_stock_order && type != "product") {
                      displayQtyOrType = type
                  }else{
                      displayQtyOrType = quantity.toFixed(2) + ' ' + uom_id[1]
                  }
                }

                if(stock_packaging){
                    let packagingQty = product.packaging_ids[1]
                    multiplesLabel = packaged_product ? `<label class="form-text">Solo multiplos de ${packagingQty}</label><input type='hidden' id='product_qty_pack' value='${packagingQty}'/><br/>`: ``;
                }

                if(type != "product"){
                    quantity = 999
                }

                list_price = list_price.toFixed(decimalPlaces)
                tbody.append(`
                    <tr class="productItem">
                        <td class="text-center"><img style="width: auto; height:70px;" src="${image}"/></td>
                        <td colspan="2">
                            <label style="font-weight: bolder;" class="name_product">${display_name}</label><br/>
                            <input type="hidden" class="val_product" value="${id}"/>
                            <label class="form-text">${priceLabel}:</label>
                            <label class="form-text price_product" style="font-weight: bolder;">${symbolBefore} ${list_price} ${symbolAfter}</label><br/>
                            <label class="form-text" style="font-weight: bolder;">${displayQtyOrType || ""}</label><input type='hidden' id="qtyAvailable" value='${quantity}'/>
                        </td>
                        <td style="width: 150px;">
                            <input type="text" class="form-control qty_product" id='qtyProduct' data-qty-available="${quantity}" placeholder="${qtyLabel}"/>
                            ${multiplesLabel}
                            <label class="form-text text-success">${msg_price || ''}</label>
                        </td>
                    </tr>
                `)
            });

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

            const products = await ajax.jsonRpc('/budget/product', 'call', domain);

            const resp = JSON.parse(products);

            if (!resp.data) return resp;

            self.products.push(...resp.data);

            return resp;
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
        _renderProducts: async (self, productCode = '', reset = false) => {
            const resp = await self._getProducts(self, productCode);
            const { data: products, stock_packaging, allow_out_of_stock_order } = resp;
            
            const tbody = $("#table_inside");

            if (reset) {
                tbody.empty();
            }

            if (self._renderNotFoundProducts(self, tbody, productCode)) return;

            self._appendProduct(self, products, allow_out_of_stock_order, stock_packaging, tbody)
        },
        _onClickSearchProduct: async function(ev) {
            if($('#search_text').val() != ''){
                const self = this;
                const productCode = $('#search_text').val()
                
                $('#search_product').attr('disabled', true)

                self.offsetTimes = 0;
                self.products = [];

                this._renderProducts(self, productCode, true);
            }
        },
        _onProductModalScroll: (self) => {
            let scrollContainer = $('#addProduct .modal-body');
            
            if (!scrollContainer.length) return;
            
            scrollContainer = scrollContainer[0]
            
            scrollContainer.addEventListener('scroll', () => {

                if (
                    scrollContainer.scrollTop + scrollContainer.clientHeight >= 
                    scrollContainer.scrollHeight
                ) {
                    const productCount = self.products.length;

                    self.offsetTimes += 1;

                    const productCode = $('#search_text').val()
                    
                    self._renderProducts(self, productCode)

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
        },

        _onClickSaveProducts: async function(ev) {
            $("#save_products").attr('disabled', true)
            const querySelector = document.querySelectorAll("#table_inside input.qty_product")

            let isPassed = false
            const orders = {
                void: null,
                withValues: [],
            };

            querySelector.forEach(input => {
                if (input.value.trim() != ''){ 
                    let address;
                    if($("#same_address").is(':checked')){
                        address = parseInt($("#billing_address").val())
                    }else{
                        address = parseInt($("#project").val())
                    }
                    const tr = $(input).closest('tr');
                    const price = parseFloat(tr.find('label.price_product').text())
                    const id = +tr.find('input.val_product').val()
                    const qty = +input.value
                    if(!$("#number_order_value").val() && !isPassed){
                        orders.void = {
                            "sale_order": {
                                "partner_id": +$("#client").val(),
                                "partner_invoice_id": +$("#billing_address").val(),
                                "partner_shipping_id": address,
                                "pricelist_id": +$("#fee_value").val(),
                                "payment_term_id": +$("#payment_terms_value").val(),
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
                        }
                        isPassed = true;
                        
                    } else {
                        orders.withValues.push({           
                            "sale_order_id":{                 
                                "id": +$("#number_order_value").val(),
                                "partner_id": +$("#client").val(),
                                "partner_invoice_id": +$("#billing_address").val(),
                                "partner_shipping_id": address,
                                "pricelist_id": +$("#fee_value").val(),
                                "payment_term_id": +$("#payment_terms_value").val(),
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
                    }
                }
            })

            if(!$("#number_order_value").val()){
                const products = await ajax.jsonRpc('/budget/order/create', 'call',
                    {"order" :orders.void}
                )
                const { status, data } = products;
                const is400e = status === 400;
                if (is400e) return 
                    
                $("#note").val("")
                $("#product_head").show()
                $("#number").show()
                $("#number_order").text(data[0].name)
                $("#number_order_value").val(data[0].id)
                $("#same_address").attr('disabled', true)
                $("#invoice").attr('disabled', false)
                // this.build_table_products(data,true)
            }

            if(orders.withValues.length > 0){
                orders.withValues.forEach(line => {
                    line.sale_order_id.id = +$("#number_order_value").val()
                })
                const products = await ajax.jsonRpc('/budget/create/order/line', 'call',
                        {"sale_orders" :orders.withValues}
                    )
                const { status:st, data:dt, msg } = products;
                const is400 = st === 400;
                if (is400){
                    $("#save_products").attr('disabled', false)
                    this._onClickExitProducts()
                    Dialog.alert(this,msg, { title: 'Error' });
                    return 
                }
                // this.build_table_products(dt,true)
            }

            this.refreshOrderLines()

            this._onClickExitProducts()
            $("#table_inside").empty()
        },

        _onClickProductQty: function(){
            $('#save_products').attr('disabled', true)
        },

        _onChangeProductQty: async function(ev) {
            let tr = ev.target.closest('tr');
            let productQtyPack = tr.querySelector('#product_qty_pack') ? tr.querySelector('#product_qty_pack').value : 1
            let productQtyInsert = tr.querySelector('#qtyProduct').value;
            let productQtyAvailable = tr.querySelector("#qtyAvailable").value
        
            const response = await ajax.jsonRpc('/validation_available', 'call', {});
            const allowOutOfStockOrder = response.allow_out_of_stock_order;
        
            if (+productQtyInsert > +productQtyAvailable && !allowOutOfStockOrder) {
                tr.querySelector('#qtyProduct').value = productQtyAvailable
                this.showError()
            }
            if (+productQtyAvailable < +productQtyPack){
                this.validateInputEmpty()
                return
            }
        
            if(productQtyInsert % productQtyPack != 0){
                tr.querySelector('#qtyProduct').value = ''
                this.showError()
            }
            this.validateInputEmpty()
        },

        showError: function( msg = "Verifica las unidades del producto"){
            $("#errorQty").modal('show')
            $("#errorQtyMsg").html(msg);
            setTimeout(function () {
                $("#errorQty").modal('hide')
            }, 2000);
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

            const resp = await ajax.jsonRpc(
                '/budget/order/line/edit', 
                'call',
                params,
                settings
            )

            const { status, msg } = resp;

            if (status === 400) {
                throw msg;
            } 

            return resp;

        },

        _check_order_line_qty_quantity: async function (ev) {
            const qty = +ev.target.value;
            const qtyAvailable = +ev.target.dataset.qtyAvailable;
            const qtyPack = +ev.target.dataset.qtyPack;

            const response = await ajax.jsonRpc('/validation_available', 'call', {});
            const allowOutOfStockOrder = response.allow_out_of_stock_order;

            if (qty > qtyAvailable && !allowOutOfStockOrder) {
                ev.target.value = qtyAvailable
                throw "La cantidad es mayor que la cantidad disponible";
            }

            if (qtyAvailable < +qtyPack){
                this.validateInputEmpty()
                throw `La cantidad disponible es menor al múltiplo de ${qtyPack}`;
            }
        
            if(qty % qtyPack != 0){
                ev.target.value = ''
                throw `La cantidad no es un múltiplo de ${qtyPack}`;
            }

            this.validateInputEmpty()

            return true;
        },

        _onChangeQtyOrderLine: async function(ev) {
            try {
                const tr = $(ev.target).closest('tr');

                if (!tr.length) return;

                await this._check_order_line_qty_quantity(ev)

                const line_id = +tr[0].dataset.id;
                const qty = +ev.target.value

                const data = {
                    line_id,
                    "product_uom_qty": qty
                }

                await this._update_order_line(data)

                await this.refreshOrderLines()

            } catch (error) {
                this.showError(error)
            }
        },

        _getElemQtyOrderLine: function (order, line) {
            const show_input = true
            const { product_uom_qty, qty_available, packaging_qty } = line;

            const label = _t("Cantidad: ");

            let elem = `
                <div class="form-group">
                    <label class="form-text" style="padding-right:3px;">${label} </label>
                    <label>
                        <input 
                            type="text"
                            style="width: 60px;"
                            class="form-control p-1 input_qty_line" 
                            value="${product_uom_qty.toFixed(2)}"
                            data-qty-available="${qty_available}"
                            data-qty-pack="${packaging_qty}"
                        />
                    </label>
                    <br/>
                    <label class="form-text" style="padding-right:3px;">Múltiplos de ${packaging_qty} </label>
                </div>
            `;

            if (show_input) return elem;

            // state == draft -> show input to type qty
            return `
                <label class="form-label" style="padding-right:3px;">
                    ${label}
                </label>
                <label class="form-label" style="font-weight: bolder;">${product_uom_qty.toFixed(2)}</label><br/>
            `;
        },

        build_table_products: async function(data,buildTax) {
            if(buildTax && $("#invoice").is(":checked")){
                this.refreshOrderLines()
                return
            }
            const tbody = $("#product_list")
            const order = data[0];
            const { order_line } = order;

            tbody.empty()

            var unitLabel = _t("Precio Unitario: ")
            const symbol = $("#symbolB").val()
            let symbolAfter = ""
            let symbolBefore = ""
            let decimalPlaces = +$("#decimal").val()
            const response = await ajax.jsonRpc('/validation_available', 'call', {});
            const allowOutOfStockOrder = response.allow_out_of_stock_order;

            if($("#positionS").val() == "after"){
                symbolAfter = symbol
            }else{
                symbolBefore = symbol
            }
            order_line.forEach(line => {
                let { tax_id, name, product_uom_qty, price_unit, price_subtotal, id, qty_available } = line
                price_unit = price_unit.toFixed(decimalPlaces) 
                price_subtotal = price_subtotal.toFixed(decimalPlaces)
                let tax = ''
                let taxValue = 0
                let msgDeletProduct = ``
                if($("#invoice").is(":checked")){
                    tax = tax_id[1]
                    taxValue = tax_id[2]
                }
                if(product_uom_qty > qty_available && !allowOutOfStockOrder){
                    msgDeletProduct = `<label class='alert-danger form-text'>Verifique cantidad disponible de productos</label><br/>`
                }
                let trash = `<button type="button" class="fa fa-trash-o delete_product cancel_confirmed_input" 
                            style="background-color: transparent;border: none;padding: 0; color:red;"></button>`

                const elem_qty_order_line = this._getElemQtyOrderLine(order, line)

                if($("#status-val").val() == 'cancel' || $("#status-val").val() == 'sale') trash = ``
                tbody.append(`
                <tr data-id="${id}">
                    <td colspan="4">
                        <label style="font-weight: bolder;">${name}</label> <input type="hidden" value="${id}"> <br/>
                        ${elem_qty_order_line}
                        ${msgDeletProduct}
                        <label class="form-text" style="padding-right:3px;">${unitLabel}</label><label class="form-text" style="font-weight: bolder;">${symbolBefore} ${price_unit} ${symbolAfter}</label><br/>
                    </td>
                    <td class="text-center">
                        <div style="display: flex; align-items: center; justify-content: center;">
                            <div style="width: 100px; height: 50px;">
                                <label class="total_product">${symbolBefore} ${price_subtotal} ${symbolAfter}</label>
                                <input type="hidden" id="value-total-product" value="${price_subtotal}"/>
                            </div>
                        </div>
                        <div>
                            <label class="badge bg-primary" id="tax-product">${tax}</label>
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
                $("#subtotal").text(data[0].amount_untaxed.toFixed(decimalPlaces) )
                $("#total").text(data[0].amount_total.toFixed(decimalPlaces) )
                this.buildTableTax()
            }else{
                $("#subtotal").empty()
                $(".invoice_end").hide()
                $("#total_base").show()
                $(".iva-remove").remove()
                $(".total").show()
                $("#total").text(data[0].amount_total.toFixed(decimalPlaces) )
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
            const { status, data } = products;
            const is400 = status === 400;
            if (is400) return
            this._onChangeInvoice(ev)
            tr.remove()
        },

        _onChangeInvoice: function(ev) {
            this.refreshOrderLines()
        },

        _onChangeNote: function(ev) {
            this.refreshOrderLines()
        },

        refreshOrderLines: async function(){
            if ($("#number_order_value").val() == '') return
            const tax_included = $("#invoice").prop('checked')
            const note = $("#note").val()
            const products = await ajax.jsonRpc('/budget/include_tax', 'call', {
                "sale_id" : parseInt($("#number_order_value").val()),
                "tax_included" : tax_included,
                "note": note
            })
            const { status, data } = products;
            const is409 = status === 409;
            if (is409) return
            this.build_table_products([data],false)
        },
        
        _onClickCancel: function(ev) {
            const confirm = "cancel"
            this.Confirm_or_Cancel_Budget(confirm)
        },

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
            $(".cancel_confirmed_input").attr("disabled", true)
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

        _onClickRegisterClient: async function(ev){
            if($("#identification").val().trim() && $("#nameClient").val().trim() && 
                $("#streetDirection").val().trim() && $("#prefixClient").val().trim() != ""){

                const registerClient = await ajax.jsonRpc('/budget/create_client', 'call', {
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
                    "parent_id": $("#client").val()
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

        _msgErrorRegisterClient: function(msg){
            $("#labelMsg").text(msg)
            $("#errorMsg").modal('show')
            setTimeout(function () {
                $("#errorMsg").modal('hide')
            }, 2500);
        },

        _onChangeVatPrefix: async function(ev){
            if($("#identification").val().trim() && $("#prefixClient").val().trim()){
                const prefix = $("#prefixClient").val()
                const vat = $("#identification").val()
                const nameClient = await ajax.jsonRpc('/budget/get_name_client', 'call', {
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

        SearchFilterInputs : async function (data, tag){
            let ver = await $.ajax({
                url: "/budget/search_filter",
                type: "GET",
                data: data,
            });
            this.onSuccessCallBack(ver, tag)
        },

        onSuccessCallBack: function(data, tag){
            $(tag).html(data);
            $(tag).append($("<option></option>").attr("value", '').text('Seleccione'))
            $.each(data, function(key, field ) {
                $(tag).append($("<option></option>").attr("value", field.id).text(field.name));
            });
        },

    })

    publicWidget.registry.portalBudgetForm = portalBudgetForm

    return portalBudgetForm;
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
