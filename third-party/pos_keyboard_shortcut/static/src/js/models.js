/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */
odoo.define('point_of_sale.pos_keyboard_shortcut', function(require) {
    'use strict';
    const { EventBus, onMounted, onWillUnmount, useComponent, useExternalListener } = owl;
    const { useListener } = require("@web/core/utils/hooks");
    const { parse } = require('web.field_utils');
    const { barcodeService } = require('@barcodes/barcode_service');
    const { _t } = require('web.core');
    const INPUT_KEYS = new Set(
        ['Delete', 'Backspace', '+1', '+2', '+5', '+10', '+20', '+50'].concat('0123456789+-.,'.split(''))
    );
    const CONTROL_KEYS = new Set(['Esc']);
    const ALLOWED_KEYS = new Set([...INPUT_KEYS, ...CONTROL_KEYS]);
    const getDefaultConfig = () => ({
        decimalPoint: false,
        triggerAtEnter: false,
        triggerAtEsc: false,
        triggerAtInput: false,
        nonKeyboardInputEvent: false,
        useWithBarcode: false,
    });
    var fired = false;
    const { Gui } = require('point_of_sale.Gui');

    /**
     * @prop {'quantiy' | 'price' | 'discount'} activeMode
     * @event set-numpad-mode - triggered when mode button is clicked
     * @event numpad-click-input - triggered when numpad button is clicked
     *
     * IMPROVEMENT: Whenever new-orderline-selected is triggered,
     * numpad mode should be set to 'quantity'. Now that the mode state
     * is lifted to the parent component, this improvement can be done in
     * the parent component.
     */
    class NumberKeyboardBuffer extends EventBus {
        constructor() {
            super();
            this.isReset = false;
            this.bufferHolderStack = [];
        }
        /**
         * @returns {String} value of the buffer, e.g. '-95.79'
         */
        get() {
            return this.state ? this.state.buffer : null;
        }
        /**
         * Takes a string that is convertible to float, and set it as
         * value of the buffer. e.g. val = '2.99';
         *
         * @param {String} val
         */
        set(val) {
            this.state.buffer = !isNaN(parseFloat(val)) ? val : '';
            this.trigger('buffer-update', this.state.buffer);
        }
        /**
         * Resets the buffer to empty string.
         */
        reset() {
            this.isReset = true;
            this.state.buffer = '';
            this.trigger('buffer-update', this.state.buffer);
        }
        /**
         * Calling this function, we immediately invoke the `handler` method
         * that handles the contents of the input events buffer (`eventsBuffer`).
         * This is helpful when we don't want to wait for the timeout that
         * is supposed to invoke the handler.
         */
        capture() {
            if (this.handler) {
                clearTimeout(this._timeout);
                this.handler();
                delete this.handler;
            }
        }
        /**
         * @returns {number} float equivalent of the value of buffer
         */
        getFloat() {
            return parse.float(this.get());
        }
        /**
         * Add keyup listener to window via the useExternalListener hook.
         * When the component calling this is unmounted, the listener is also
         * removed from window.
         */
        activate() {
            this.defaultDecimalPoint = _t.database.parameters.decimal_point;
            useExternalListener(window, 'keyup', this._onKeyboardInput.bind(this));
        }
        /**
         * @param {Object} config Use to setup the buffer
         * @param {String|null} config.decimalPoint The decimal character.
         * @param {String|null} config.triggerAtEnter Event triggered when 'Enter' key is pressed.
         * @param {String|null} config.triggerAtEsc Event triggered when 'Esc' key is pressed.
         * @param {String|null} config.triggerAtInput Event triggered for every accepted input.
         * @param {String|null} config.nonKeyboardInputEvent Also listen to a non-keyboard input event
         *      that carries a payload of { key }. The key is checked if it is a valid input. If valid,
         *      the number buffer is modified just as it is modified when a keyboard key is pressed.
         * @param {Boolean} config.useWithBarcode Whether this buffer is used with barcode.
         * @emits config.triggerAtEnter when 'Enter' key is pressed.
         * @emits config.triggerAtEsc when 'Esc' key is pressed.
         * @emits config.triggerAtInput when an input is accepted.
         */
        use(config) {
            this.eventsBuffer = [];
            const currentComponent = useComponent();
            config = Object.assign(getDefaultConfig(), config);
            onMounted(() => {
                this.bufferHolderStack.push({
                    component: currentComponent,
                    state: config.state ? config.state : { buffer: '', toStartOver: false },
                    config,
                });
                this._setUp();
            });
            onWillUnmount(() => {
                this.bufferHolderStack.pop();
                this._setUp();
            });
            // Add listener that accepts non keyboard inputs
            if (typeof config.nonKeyboardInputEvent === 'string') {
                useListener(config.nonKeyboardInputEvent, this._onNonKeyboardInput.bind(this));
            }
        }
        get _currentBufferHolder() {
            return this.bufferHolderStack[this.bufferHolderStack.length - 1];
        }
        _setUp() {
            if (!this._currentBufferHolder) return;
            const { component, state, config } = this._currentBufferHolder;
            this.component = component;
            this.state = state;
            this.config = config;
            this.decimalPoint = config.decimalPoint || this.defaultDecimalPoint;
            this.maxTimeBetweenKeys = this.config.useWithBarcode
                ? barcodeService.maxTimeBetweenKeysInMs
                : 0;
        }
        _onKeyboardInput(event) {
            return this._bufferEvents(this._onInput(event => event.key))(event);
        }
        _onNonKeyboardInput(event) {
            return this._bufferEvents(this._onInput(event => event.detail.key))(event);
        }
        _bufferEvents(handler) {
            return event => {
                if (['INPUT', 'TEXTAREA'].includes(event.target.tagName) || !this.eventsBuffer) return;
                clearTimeout(this._timeout);
                this.eventsBuffer.push(event);
                this._timeout = setTimeout(handler, this.maxTimeBetweenKeys);
                this.handler = handler
            };
        }
        _onInput(keyAccessor) {
            var self = this;
            return () => {
                if (this.eventsBuffer.length <= 2) {
                    // Check first the buffer if its contents are all valid
                    // number input.
                    for (let event of this.eventsBuffer) {
                        if (!ALLOWED_KEYS.has(keyAccessor(event))) {
                            this.eventsBuffer = [];
                            self.perform_event(event);
                            return;
                        }
                    }
                    // At this point, all the events in buffer
                    // contains number input. It's now okay to handle
                    // each input.
                    for (let event of this.eventsBuffer) {
                        this._handleInput(keyAccessor(event));
                        event.preventDefault();
                        event.stopPropagation();
                    }
                }
                this.eventsBuffer = [];
            };
        }
        _handleInput(key) {
            if (key === 'Enter' && this.config.triggerAtEnter) {
                this.component.trigger(this.config.triggerAtEnter, this.state);
            } else if (key === 'Esc' && this.config.triggerAtEsc) {
                this.component.trigger(this.config.triggerAtEsc, this.state);
            } else if (INPUT_KEYS.has(key)) {
                this._updateBuffer(key);
                if (this.config.triggerAtInput && this.component)
                    this.component.trigger(this.config.triggerAtInput, { buffer: this.state.buffer, key });
            }
        }
        /**
         * Updates the current buffer state using the given input.
         * @param {String} input valid input
         */
         _updateBuffer(input) {
            const isEmpty = val => {
                return val === '' || val === null;
            };
            if (input === undefined || input === null) return;
            let isFirstInput = isEmpty(this.state.buffer);
            if (input === ',' || input === '.') {
                if (this.state.toStartOver) {
                    this.state.buffer = '';
                }
                if (isFirstInput) {
                    this.state.buffer = '0' + this.decimalPoint;
                } else if (!this.state.buffer.length || this.state.buffer === '-') {
                    this.state.buffer += '0' + this.decimalPoint;
                } else if (this.state.buffer.indexOf(this.decimalPoint) < 0) {
                    this.state.buffer = this.state.buffer + this.decimalPoint;
                }
            } else if (input === 'Delete') {
                if (this.isReset) {
                    this.state.buffer = '';
                    this.isReset = false;
                    return;
                }
                this.state.buffer = isEmpty(this.state.buffer) ? null : '';
            } else if (input === 'Backspace') {
                if (this.isReset) {
                    this.state.buffer = '';
                    this.isReset = false;
                    return;
                }
                if (this.state.toStartOver) {
                    this.state.buffer = '';
                }
                const buffer = this.state.buffer;
                if (isEmpty(buffer)) {
                    this.state.buffer = null;
                } else {
                    const nCharToRemove = buffer[buffer.length - 1] === this.decimalPoint ? 2 : 1;
                    this.state.buffer = buffer.substring(0, buffer.length - nCharToRemove);
                }
            } else if (input === '+') {
                if (this.state.buffer[0] === '-') {
                    this.state.buffer = this.state.buffer.substring(1, this.state.buffer.length);
                }
            } else if (input === '-') {
                if (isFirstInput) {
                    this.state.buffer = '-0';
                } else if (this.state.buffer[0] === '-') {
                    this.state.buffer = this.state.buffer.substring(1, this.state.buffer.length);
                } else {
                    this.state.buffer = '-' + this.state.buffer;
                }
            } else if (input[0] === '+' && !isNaN(parseFloat(input))) {
                // when input is like '+10', '+50', etc
                const inputValue = parse.float(input.slice(1));
                const currentBufferValue = this.state.buffer ? parse.float(this.state.buffer) : 0;
                this.state.buffer = this.component.env.pos.formatFixed(
                    inputValue + currentBufferValue
                );
            } else if (!isNaN(parseInt(input, 10))) {
                if (this.state.toStartOver) {  // when we want to erase the current buffer for a new value
                    this.state.buffer = '';
                }
                if (isFirstInput) {
                    this.state.buffer = '' + input;
                } else if (this.state.buffer.length > 12) {
                    Gui.playSound('bell');
                } else {
                    this.state.buffer += input;
                }
            }
            if (this.state.buffer === '-') {
                this.state.buffer = '';
            }
            // once an input is accepted and updated the buffer,
            // the buffer should not be in reset state anymore.
            this.isReset = false;
            // it should not be in a start the buffer over state anymore.
            this.state.toStartOver = false;

            this.trigger('buffer-update', this.state.buffer);
        }
        scroll_cashier(shortcut_pressed){
            if(shortcut_pressed == 'ARROWDOWN'){
                if($('.selection-item').hasClass('selected')){
                    var current = $('.selection-item.selected')
                    if(current.next().hasClass('selection-item')){
                        current.next().addClass('selected');
                        current.removeClass('selected');
                        var index = $('.selection-item.selected').index();
                        $('.selection.scrollable-y').animate({
                            scrollTop: 50*index
                        },50);
                    } else {
                        current.removeClass('selected')
                        $('.selection.scrollable-y div:first-child').addClass('selected')
                        $('.selection.scrollable-y').animate({
                            scrollTop: 0
                        },50);
                    }
                }
                else
                    $('.selection.scrollable-y div:first-child').addClass('selected')
            }
            if(shortcut_pressed == 'ARROWUP'){
                if($('.selection-item').hasClass('selected')){
                    var current = $('.selection-item.selected')
                    if(current.prev().hasClass('selection-item')){
                        current.prev().addClass('selected');
                        current.removeClass('selected');
                        var index = $('.selection-item.selected').index();
                        $('.selection.scrollable-y').animate({
                            scrollTop: 50*index
                        },50);
                    } else {
                        current.removeClass('selected')
                        $('.selection.scrollable-y div:last-child').addClass('selected')
                        var index = $('.selection-item.selected').index();
                        $('.selection.scrollable-y').animate({
                            scrollTop: 50*index
                        },50);
                    }
                }
                else
                    $('.selection.scrollable-y div:first-child').addClass('selected')
            }
        }
        remove_classes(){
            $('.actionpad button:nth-child(1)').removeClass('overlay')
            $('.button.set-partner').removeClass('overlay')
            $('.button.pay').removeClass('overlay')
            $("button.mode-button:contains(Qty)").removeClass('overlay');
            $("button.mode-button:contains(Disc)").removeClass('overlay');
            $("button.mode-button:contains(Price)").removeClass('overlay');
            $('.username').parent().parent().removeClass('overlay')
            $('.button.new-customer').removeClass('overlay')
            $('.button.back').removeClass('overlay')
            $(".button.paymentmethod").removeClass('overlay')
            $('.button.print').removeClass('overlay');
            $(".fa.fa-fw").parent().parent().removeClass('overlay')
            $(".header-button").removeClass('overlay')
            $(".header-button.lock-button").removeClass('overlay')
            $(".ticket-button").removeClass('overlay')
            $(".pads .control-buttons .control-button:contains(Info)").removeClass('overlay')
            $(".pads .control-buttons .control-button:contains(Refund)").removeClass('overlay')
            $('.hidden_tags').hide();
            $('.hidden_tags_header').hide();
            $('.button.back').removeClass('overlay');
            $(".button.print").removeClass('overlay');
            $(".button.next").removeClass('overlay');
            $(".button.js_invoice").removeClass('overlay');
            $(".partner-button .button").removeClass('overlay');
            $(".button.next").removeClass('overlay');
            return false
        }
        perform_event(e){
            var self = this;
            if(window.posmodel.config.enable_shortcuts){
                var product_screen = $(".product-screen.screen").is(':visible');
                var payment_screen = $(".payment-screen.screen").is(':visible');
                var clientlist_screen = $(".partnerlist-screen.screen").is(':visible');
                var receipt_screen = $(".receipt-screen.screen").is(':visible');
                var ticket_screen = $(".ticket-screen.screen").is(':visible');
                var shortcut_pressed = e.key.toUpperCase();
                var all_shortcuts = window.posmodel.db.shortcuts_by_id[window.posmodel.config.select_shortcut[0]];
                if (product_screen){
                    var is_popup = $("div.popups").is(":visible")
                    if(e.keyCode == 17){
                        if(fired){
                            fired = false;
                            self.remove_classes();
                        } else {  
                            fired = true;
                            var all_shortcuts = window.posmodel.db.shortcuts_by_id[window.posmodel.config.select_shortcut[0]];
                            if(all_shortcuts.customer_screen){
                                $('.button.set-partner span').html(all_shortcuts.customer_screen.toUpperCase())
                                $('.button.set-partner').addClass('overlay');
                            }
                            if(all_shortcuts.next_screen){
                                $('.button.pay span:last-child').html(all_shortcuts.next_screen.toUpperCase())                                   
                                $('.button.pay').addClass('overlay');                                                                         
                            }
                            if(all_shortcuts.select_qty){
                                $("button.mode-button:contains(Qty) span").html(all_shortcuts.select_qty.toUpperCase())
                                $("button.mode-button:contains(Qty)").addClass('overlay');
                            }
                            if(all_shortcuts.select_discount){
                                $("button.mode-button:contains(Disc) span").html(all_shortcuts.select_discount.toUpperCase())
                                $("button.mode-button:contains(Disc)").addClass('overlay');               
                            }
                            if(all_shortcuts.select_info){
                                $(".pads .control-buttons .control-button:contains(Info) span").html(all_shortcuts.select_info.toUpperCase())
                                $(".pads .control-buttons .control-button:contains(Info)").addClass('overlay');               
                            }
                            if(all_shortcuts.select_refund){
                                $(".pads .control-buttons .control-button:contains(Refund) span").html(all_shortcuts.select_refund.toUpperCase())
                                $(".pads .control-buttons .control-button:contains(Refund)").addClass('overlay');               
                            }
                            if(all_shortcuts.select_price){
                                $("button.mode-button:contains(Price) span").html(all_shortcuts.select_price.toUpperCase())
                                $("button.mode-button:contains(Price)").addClass('overlay');
                            }
                            if(all_shortcuts.select_user){
                                if(window.posmodel.config.module_pos_hr && (window.posmodel.employees && window.posmodel.employees.length)){
                                    if($('span.username span').length == 0){
                                        $('span.username').append('<span class="hidden_tags" style="font-size:15px;"></span>');
                                    }
                                    $('span.username span').html(all_shortcuts.select_user.toUpperCase());
                                    $('span.username').parent().parent().addClass('overlay')
                                }
                            }
                            if(all_shortcuts.refresh){
                                $(".fa.fa-fw").parent().parent().find('.hidden_tags').html(all_shortcuts.refresh.toUpperCase())
                                $(".fa.fa-fw").parent().parent().addClass('overlay')
                            }
                            if(all_shortcuts.see_all_order){
                                $(".ticket-button div:nth-child(2) span").html(all_shortcuts.see_all_order.toUpperCase());
                                $(".ticket-button").addClass('overlay')
                            }
                            if(all_shortcuts.close_pos && $('.header-button').length){
                                if($('.header-button.lock-button').length){
                                    if($('.header-button.lock-button .hidden_tags').length == 0){
                                        $('.header-button.lock-button').append('<span class="hidden_tags" style="font-size:15px;"></span>');
                                    }
                                    $('.header-button.lock-button .hidden_tags').html(all_shortcuts.close_pos.toUpperCase());
                                    $(".header-button.lock-button").addClass('overlay')
                                    $(".pos-rightheader").animate({scrollLeft: 50});
                                } else {
                                    if($('.header-button .hidden_tags').length == 0){
                                        $('.header-button').append('<span class="hidden_tags" style="font-size:15px;"></span>');
                                    }
                                    $('.header-button .hidden_tags').html(all_shortcuts.close_pos.toUpperCase());
                                    $(".header-button").addClass('overlay')
                                }
                            }
                            $('.hidden_tags').show();
                            $('.hidden_tags_header').show();
                        }
                    } else {
                        if(!is_popup){
                            if(all_shortcuts.next_screen && (shortcut_pressed == all_shortcuts.next_screen.toUpperCase())){
                                e.preventDefault();
                                $('.button.pay').click();
                                fired = self.remove_classes();
                            }
                            if(all_shortcuts.customer_screen && (shortcut_pressed == all_shortcuts.customer_screen.toUpperCase())){
                                e.preventDefault();
                                $('.button.set-partner').click();
                                setTimeout(function(){
                                    $('.searchbox-client input').focus();
                                },50);
                                fired = self.remove_classes();
                            }
                            if(all_shortcuts.create_customer && (shortcut_pressed == all_shortcuts.create_customer.toUpperCase())){
                                e.preventDefault();
                                $('.button.set-partner').click();
                                setTimeout(function(){
                                    $('.button.new-customer').click();
                                    setTimeout(function(){
                                        $(".search-bar-container .pos-search-bar input").focus();
                                    },100);
                                },100);
                                fired = self.remove_classes();
                            }
                            if(all_shortcuts.search_product && (shortcut_pressed == all_shortcuts.search_product.toUpperCase())){
                                e.preventDefault();
                                $(".products-widget-control .pos-search-bar input").focus();
                                fired = self.remove_classes();
                            }
                            if(all_shortcuts.select_qty && (shortcut_pressed == all_shortcuts.select_qty.toUpperCase())){
                                e.preventDefault();
                                $("button.mode-button:contains(Qty)").click();
                                fired = self.remove_classes();
                            }
                            if(all_shortcuts.select_discount && (shortcut_pressed == all_shortcuts.select_discount.toUpperCase())){
                                e.preventDefault();
                                $("button.mode-button:contains(Disc)").click();
                                fired = self.remove_classes();
                            }
                            if(all_shortcuts.select_info && (shortcut_pressed == all_shortcuts.select_info.toUpperCase())){
                                e.preventDefault();
                                $(".pads .control-buttons .control-button:contains(Info)").click();
                                fired = self.remove_classes();
                            }
                            if(all_shortcuts.select_refund && (shortcut_pressed == all_shortcuts.select_refund.toUpperCase())){
                                e.preventDefault();
                                $(".pads .control-buttons .control-button:contains(Refund)").click();
                                fired = self.remove_classes();
                            } 
                            if(all_shortcuts.select_price && (shortcut_pressed == all_shortcuts.select_price.toUpperCase())){
                                e.preventDefault();
                                $("button.mode-button:contains(Price)").click();
                                fired = self.remove_classes();
                            }
                            if(all_shortcuts.see_all_order && (shortcut_pressed == all_shortcuts.see_all_order.toUpperCase())){
                                e.preventDefault();
                                $("div.ticket-button").click();
                                fired = self.remove_classes();
                            }
                            if(all_shortcuts.select_user && (shortcut_pressed == all_shortcuts.select_user.toUpperCase())){
                                e.preventDefault();
                                $("span.username").click();
                                fired = self.remove_classes();
                            }
                            if(all_shortcuts.refresh && (shortcut_pressed == all_shortcuts.refresh.toUpperCase())){
                                e.preventDefault();
                                $(".fa.fa-fw").parent().parent().click()
                                fired = self.remove_classes();
                            }
                            if($(".header-button").length){
                                if(all_shortcuts.close_pos && (shortcut_pressed == all_shortcuts.close_pos.toUpperCase())){
                                    e.preventDefault();
                                    $(".header-button").click();
                                    fired = self.remove_classes();
                                }
                            }
                            if($('.product-list article').is(':focus')){
                                if(e.key.toUpperCase() == all_shortcuts.navigate_product_right.toUpperCase()){
                                    if(document.activeElement.nextSibling && document.activeElement.nextSibling.className == 'product')
                                        document.activeElement.nextSibling.focus();
                                    else
                                        $('.product-list article:first-child').focus();
                                }
                                if(e.key.toUpperCase() == all_shortcuts.navigate_product_left.toUpperCase()){
                                    if(document.activeElement.previousSibling && document.activeElement.previousSibling.className == 'product')
                                        document.activeElement.previousSibling.focus();
                                    else
                                        $('.product-list article:last-child').focus();
                                }
                                if(e.key.toUpperCase() == 'ARROWUP' || e.key.toUpperCase() == 'ARROWDOWN'){
                                    $( "div .product-list article:focus" ).blur()
                                    $(".orderline.selected").focus()
                                }
                                if(e.key.toUpperCase() == 'ENTER'){
                                    if($(".product").is(":focus") && e.keyCode == 13 && document.activeElement && (document.activeElement.className == 'product')){
                                        let product_id = document.activeElement.getAttribute('data-product-id');
                                        $("[data-product-id~='"+product_id+"']").click();
                                        $("[data-product-id~='"+product_id+"']").focus();
                                    }
                                }
                                fired = self.remove_classes();
                            }
                            if(!$('.product-list article').is(':focus')){
                                if(e.key.toUpperCase() == 'ARROWUP'){
                                    if($('li.orderline.selected').length){
                                        $('li.orderline.selected').prev().click();
                                        if($('li.orderline.selected').prev().length){
                                            $('.product-screen.screen .order-container').animate({
                                                scrollTop: $('li.orderline.selected').offset().top - $('.product-screen.screen .order-container').offset().top - $('.product-screen.screen .order-container').offset().top - $('.product-screen.screen .order-container').offset().top + $('.product-screen.screen .order-container').scrollTop()
                                            },50);
                                        }
                                    }
                                }
                                if(e.key.toUpperCase() == 'ARROWDOWN'){
                                    if($('li.orderline.selected').length){
                                        $('li.orderline.selected').next().click();
                                        if($('li.orderline.selected').next().length){
                                            $('.product-screen.screen .order-container').animate({
                                                scrollTop: $('li.orderline.selected').offset().top - $('.product-screen.screen .order-container').offset().top + $('.product-screen.screen .order-container').scrollTop()
                                            },50);
                                        }
                                    }
                                }
                                if(e.key.toUpperCase() == 'ARROWLEFT' || e.key.toUpperCase() == 'ARROWRIGHT'){
                                    $( "div .product-list article:first-child" ).focus()
                                    $(".orderline.selected").blur()
                                }
                                fired = self.remove_classes();
                            }
                        } else {
                            // Employee Selection
                            if(shortcut_pressed == 'ARROWDOWN'){
                                self.scroll_cashier(shortcut_pressed);
                            }
                            if(shortcut_pressed == 'ARROWUP'){
                                self.scroll_cashier(shortcut_pressed);
                            }
                            if(shortcut_pressed == 'ENTER'){
                                if($('.selection-item.selected').is(":visible")){
                                    $('.selection-item.selected').click();
                                } else {
                                    $('.button.confirm').click();
                                }
                            }
                        }
                    }
                }
                else if(ticket_screen){
                    var is_popup = $("div.popups").is(":visible")
                    if(!is_popup){
                        if(all_shortcuts.back_screen && (shortcut_pressed == all_shortcuts.back_screen.toUpperCase())){
                            e.preventDefault();
                            $('button.discard').click();
                        }
                        if(all_shortcuts.search_product && (shortcut_pressed == all_shortcuts.search_product.toUpperCase())){
                            e.preventDefault();
                            $(".rightpane.pane-border .search input").focus();
                        }
                    } else {
                        if(shortcut_pressed == 'ENTER'){
                            if($('.selection-item.selected').is(":visible")){
                                $('.selection-item.selected').click();
                            } else {
                                $('.button.confirm').click();
                            }
                        }
                    }
                }
                else if(clientlist_screen){
                    var is_popup = $("div.popups").is(":visible")
                    if(e.keyCode == 17){
                        if(fired){
                            fired = false;
                            self.remove_classes();
                        } else {  
                            fired = true;
                            var all_shortcuts = window.posmodel.db.shortcuts_by_id[window.posmodel.config.select_shortcut[0]];
                            if(all_shortcuts.back_screen){
                                $(".button.back span").html(all_shortcuts.back_screen.toUpperCase());
                                $(".button.back").addClass('overlay')
                            }
                            if(all_shortcuts.create_customer){
                                $(".button.new-customer span").html(all_shortcuts.create_customer.toUpperCase());
                                $(".button.new-customer").addClass('overlay')
                            }
                            $('.hidden_tags').show();
                            $('.hidden_tags_header').show();
                        }
                    }
                    if(!is_popup){
                        if(all_shortcuts.back_screen && (shortcut_pressed == all_shortcuts.back_screen.toUpperCase())){
                            e.preventDefault();
                            $('.button.back').click();
                        }
                        if(all_shortcuts.search_product && (shortcut_pressed == all_shortcuts.search_product.toUpperCase())){
                            e.preventDefault();
                            $(".search-bar-container .pos-search-bar input").focus();
                        }
                        if(all_shortcuts.create_customer && (shortcut_pressed == all_shortcuts.create_customer.toUpperCase())){
                            e.preventDefault();
                            $('.button.new-customer').click();
                            fired = self.remove_classes();
                        }
                        // if(e.key.toUpperCase() == 'ARROWDOWN'){
                        //     if($('.partner-list .partner-list-contents .highlight').length){
                        //         $('.partner-list .partner-list-contents .highlight').next().click();
                        //         if($('.partner-list .partner-list-contents .highlight').offset() && $('.subwindow-container-fix.touch-scrollable.scrollable-y').offset()){
                        //             $('.subwindow-container-fix.touch-scrollable.scrollable-y').animate({
                        //                 scrollTop: $('.partner-list .partner-list-contents .highlight').offset().top - $('.subwindow-container-fix.touch-scrollable.scrollable-y').offset().top + $('.subwindow-container-fix.touch-scrollable.scrollable-y').scrollTop()
                        //             },50);
                        //         }
                        //     }
                        //     else
                        //         $('.partner-list .partner-list-contents tr:first-child').click()
                        // }
                        // if(e.key.toUpperCase() == 'ARROWUP'){
                        //     if($('.partner-list .partner-list-contents .highlight').length){
                        //         $('.partner-list .partner-list-contents .highlight').prev().click();
                        //         if($('.partner-list .partner-list-contents .highlight').offset() && $('.subwindow-container-fix.touch-scrollable.scrollable-y').offset()){
                        //             $('.subwindow-container-fix.touch-scrollable.scrollable-y').animate({
                        //                 scrollTop: $('.partner-list .partner-list-contents .highlight').offset().top - $('.subwindow-container-fix.touch-scrollable.scrollable-y').offset().top + $('.subwindow-container-fix.touch-scrollable.scrollable-y').scrollTop()
                        //             },50)
                        //         }
                        //     }
                        //     else
                        //         $('.partner-list .partner-list-contents tr:first-child').click()
                        // }
                        // if(e.key.toUpperCase() == 'ENTER'){
                        //     if($(".partner-line.highlight").is(":visible")){
                        //         $('.button.next.highlight').click()
                        //     }
                        // }
                    } else {
                        if(shortcut_pressed == 'ENTER'){
                            if($('.selection-item.selected').is(":visible")){
                                $('.selection-item.selected').click();
                            } else {
                                $('.button.confirm').click();
                            }
                        }
                    }
                }
                else if(payment_screen){
                    var is_popup = $("div.popups").is(":visible")
                    // CONTROL_KEYS == 17
                    if(e.keyCode == 17){
                        if(fired){
                            fired = false;
                            self.remove_classes();
                        } else {  
                            fired = true;
                            var all_shortcuts = window.posmodel.db.shortcuts_by_id[window.posmodel.config.select_shortcut[0]];
                            if(all_shortcuts.select_user){
                                $('.pos-rightheader span.wk_cashier.hidden_tags').html(all_shortcuts.select_user.toUpperCase());
                                $('span.username').parent().parent().addClass('overlay')
                            }
                            if(all_shortcuts.refresh){
                                $(".status-buttons .oe_status .fa.fa-fw").parent().parent().find('.hidden_tags').html(all_shortcuts.refresh.toUpperCase())
                                $(".status-buttons .oe_status .fa.fa-fw").parent().parent().addClass('overlay')
                            }
                            if(all_shortcuts.see_all_order){
                                $(".ticket-button div:nth-child(2) span").html(all_shortcuts.see_all_order.toUpperCase());
                                $(".ticket-button").addClass('overlay')
                            }
                            if(all_shortcuts.close_pos && $('.header-button').length){
                                if($('.header-button.lock-button').length){
                                    if($('.header-button.lock-button .hidden_tags').length == 0){
                                        $('.header-button.lock-button').append('<span class="hidden_tags" style="font-size:15px;"></span>');
                                    }
                                    $('.header-button.lock-button .hidden_tags').html(all_shortcuts.close_pos.toUpperCase());
                                    $(".header-button.lock-button").addClass('overlay')
                                    $(".pos-rightheader").animate({scrollLeft: 50});
                                } else {
                                    if($('.header-button .hidden_tags').length == 0){
                                        $('.header-button').append('<span class="hidden_tags" style="font-size:15px;"></span>');
                                    }
                                    $('.header-button .hidden_tags').html(all_shortcuts.close_pos.toUpperCase());
                                    $(".header-button").addClass('overlay')
                                }
                            }
                            if(all_shortcuts.back_screen){
                                $(".button.back span.hidden_tags").html(all_shortcuts.back_screen.toUpperCase());
                                $(".button.back").addClass('overlay')
                            }
                            if(all_shortcuts.order_invoice){
                                $(".button.js_invoice span.hidden_tags").html(all_shortcuts.order_invoice.toUpperCase());
                                $(".button.js_invoice").addClass('overlay')
                            }
                            if(all_shortcuts.customer_screen){
                                $(".partner-button .button span.hidden_tags").html(all_shortcuts.customer_screen.toUpperCase());
                                $(".partner-button .button").addClass('overlay')
                            }
                            if ($(".button.next").is(':visible')){
                                $(".button.next span.hidden_tags").html('ENTER');
                                $(".button.next").addClass('overlay')
                            }
                            var journal_key_shortcuts = []
                            _.each(window.posmodel.journal_key,function(value){
                                var dict_values = {
                                    'id'  : value.payment_method_id[0],
                                    'key' : value.key_journals,
                                    'name' : value.payment_method_id[1],
                                }
                                journal_key_shortcuts.push(dict_values);
                            });
                            _.each(journal_key_shortcuts, function(value){
                                if(value.key){
                                    $(".paymentmethods .payment-name:contains("+value.name+") .hidden_tags").html(value.key)
                                    $(".paymentmethods .payment-name:contains("+value.name+")").parent().addClass('overlay')
                                }
                            });
                            $('.hidden_tags').show();
                            $('.hidden_tags_header').show();
                        }
                    }
                    if(!is_popup){
                        if(all_shortcuts.back_screen && (shortcut_pressed == all_shortcuts.back_screen.toUpperCase())){
                            e.preventDefault();
                            $('.button.back').click();
                            fired = self.remove_classes();
                        }
                        if(all_shortcuts.customer_screen && (shortcut_pressed ==  all_shortcuts.customer_screen.toUpperCase())){
                            e.preventDefault();
                            $('.partner-button .button').click();
                            setTimeout(function(){
                                $(".search-bar-container .pos-search-bar input").focus();
                                fired = self.remove_classes();
                            },50);                       
                        }
                        if(all_shortcuts.order_invoice && (shortcut_pressed == all_shortcuts.order_invoice.toUpperCase())){
                            e.preventDefault();
                            $('.button.js_invoice').click();
                            fired = self.remove_classes();
                        }
                        if(all_shortcuts.see_all_order && (shortcut_pressed == all_shortcuts.see_all_order.toUpperCase())){
                            e.preventDefault();
                            $("div.ticket-button").click();
                            fired = self.remove_classes();
                        }
                        if(all_shortcuts.select_user && (shortcut_pressed == all_shortcuts.select_user.toUpperCase())){
                            e.preventDefault();
                            $("span.username").click();
                            fired = self.remove_classes();
                        }
                        if(all_shortcuts.refresh && (shortcut_pressed == all_shortcuts.refresh.toUpperCase())){
                            e.preventDefault();
                            $(".fa.fa-fw").parent().parent().click()
                            fired = self.remove_classes();
                        }
                        if($('.header-button.close_button').length){
                            if(all_shortcuts.close_pos && (shortcut_pressed == all_shortcuts.close_pos.toUpperCase())){
                                e.preventDefault();
                                $(".header-button").click();
                                fired = self.remove_classes();
                            }
                        }
                        if(e.key.toUpperCase() == 'ENTER'){
                            if($(".button.next").is(":visible")){
                                $('.button.next').click()
                            }
                            fired = self.remove_classes();
                        }
                        var journal_key_shortcuts = []
                        _.each(window.posmodel.journal_key,function(value){
                            var dict_values = {
                                'id'  : value.payment_method_id[0],
                                'key' : value.key_journals,
                                'name' : value.payment_method_id[1],
                            }
                            journal_key_shortcuts.push(dict_values);
                        });
                        _.each(journal_key_shortcuts, function(value){
                            if(value.key && (value.key.toUpperCase() == shortcut_pressed)){
                                fired = self.remove_classes();
                                $(".paymentmethods .payment-name:contains("+value.name+")").parent().click()
                            }
                        });
                    } else {
                        // Employee Selection
                        if(shortcut_pressed == 'ARROWDOWN'){
                            self.scroll_cashier(shortcut_pressed);
                        }
                        if(shortcut_pressed == 'ARROWUP'){
                            self.scroll_cashier(shortcut_pressed);
                        }
                        if(shortcut_pressed == 'ENTER'){
                            $('.button.confirm').click();
                        }
                    }
                }
                else if(receipt_screen){
                    var is_popup = $("div.popups").is(":visible")
                    if(e.keyCode == 17){
                        if(fired){
                            fired = false;
                            self.remove_classes();
                        } else {  
                            fired = true;
                            var all_shortcuts = window.posmodel.db.shortcuts_by_id[window.posmodel.config.select_shortcut[0]];
                            if(all_shortcuts.select_user){
                                $('span.username span').html(all_shortcuts.select_user.toUpperCase());
                                $('span.username').parent().parent().addClass('overlay')
                            }
                            if(all_shortcuts.refresh){
                                $(".fa.fa-fw").parent().parent().find('.hidden_tags').html(all_shortcuts.refresh.toUpperCase())
                                $(".fa.fa-fw").parent().parent().addClass('overlay')
                            }
                            if(all_shortcuts.see_all_order){
                                $(".ticket-button div:nth-child(2) span").html(all_shortcuts.see_all_order.toUpperCase());
                                $(".ticket-button").addClass('overlay')
                            }
                            if(all_shortcuts.close_pos && $('.header-button').length){
                                if($('.header-button.lock-button').length){
                                    if($('.header-button.lock-button .hidden_tags').length == 0){
                                        $('.header-button.lock-button').append('<span class="hidden_tags" style="font-size:15px;"></span>');
                                    }
                                    $('.header-button.lock-button .hidden_tags').html(all_shortcuts.close_pos.toUpperCase());
                                    $(".header-button.lock-button").addClass('overlay')
                                    $(".pos-rightheader").animate({scrollLeft: 50});
                                } else {
                                    if($('.header-button .hidden_tags').length == 0){
                                        $('.header-button').append('<span class="hidden_tags" style="font-size:15px;"></span>');
                                    }
                                    $('.header-button .hidden_tags').html(all_shortcuts.close_pos.toUpperCase());
                                    $(".header-button").addClass('overlay')
                                }
                            }
                            if(all_shortcuts.back_screen){
                                $(".button.back span.hidden_tags").html(all_shortcuts.back_screen.toUpperCase());
                                $(".button.back").addClass('overlay')
                            }
    
                            if(all_shortcuts.print_receipt){
                                $(".button.print span.hidden_tags").html(all_shortcuts.print_receipt.toUpperCase());
                                $(".button.print").addClass('overlay')
                            }
                            if(all_shortcuts.next_screen_show){
                                $(".button.next span.hidden_tags").html(all_shortcuts.next_screen_show.toUpperCase());
                                $(".button.next").addClass('overlay')
                            }
                            $('.hidden_tags').show();
                            $('.hidden_tags_header').show();
                        }
                    }
                    if(!is_popup){
                        if(all_shortcuts.next_screen_show && (shortcut_pressed == all_shortcuts.next_screen_show.toUpperCase())){
                            e.preventDefault();
                            $(".button.next").click();
                            fired = self.remove_classes();
                        }
                        if(all_shortcuts.print_receipt && (shortcut_pressed == all_shortcuts.print_receipt.toUpperCase())){
                            e.preventDefault();
                            $(".button.print").click();
                            fired = self.remove_classes();
                        }
                    } else {
                        if(shortcut_pressed == 'ENTER'){
                            $('.button.confirm').click();
                        }
                    }
                } else {
                    var is_popup = $("div.popups").is(":visible")
                    if(e.keyCode == 17){
                        if(fired){
                            fired = false;
                            self.remove_classes();
                        } else {  
                            fired = true;
                            var all_shortcuts = window.posmodel.db.shortcuts_by_id[window.posmodel.config.select_shortcut[0]];
                            if(all_shortcuts.back_screen){
                                $(".button.back span.hidden_tags").html(all_shortcuts.back_screen.toUpperCase());
                                $(".button.back").addClass('overlay')
                            }
                            $('.hidden_tags').show();
                            $('.hidden_tags_header').show();
                        }
                    }
                    if(!is_popup){
                        if(all_shortcuts.back_screen && (shortcut_pressed == all_shortcuts.back_screen.toUpperCase())){
                            e.preventDefault();
                            $('.button.back').click();
                            fired = self.remove_classes();
                        }
                    } else {
                        if(shortcut_pressed == 'ENTER'){
                            $('.button.confirm').click();
                        }
                    }
                }
            }
        }
    }
    return new NumberKeyboardBuffer();
});
