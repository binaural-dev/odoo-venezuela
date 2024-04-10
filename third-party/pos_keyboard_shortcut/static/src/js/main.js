/* Copyright (c) 2016-Present Webkul Software Pvt. Ltd. (<https://webkul.com/>) */
/* See LICENSE file for full copyright and licensing details. */
/* License URL : <https://store.webkul.com/license.html/> */
odoo.define('pos_keyboard_shortcut.pos_keyboard_shortcut', function(require){
    "use strict";       
    const Registries = require('point_of_sale.Registries');
    const Chrome = require('point_of_sale.Chrome');
    const ProductScreen = require('point_of_sale.ProductScreen');
    const NumberBufferShortcut = require('point_of_sale.pos_keyboard_shortcut');
    var { PosGlobalState } = require('point_of_sale.models');

    const PosOrders = (PosGlobalState) => class PosOrders extends PosGlobalState {
        async _processData(loadedData) {
            await super._processData(...arguments);
            await this._loadPosKeyboardShortcuts(loadedData['pos.keyboard.shortcuts'])
            await this._loadPosPaymentMethodKey(loadedData['pos.payment.method.key'])
        }
        _loadPosKeyboardShortcuts(shortcuts){
            var self = this;
            self.db.shortcut = false
            self.db.shortcuts_by_id = {};
            _.each(shortcuts, function(shortcut){
                self.db.shortcuts_by_id[shortcut.id] = shortcut;
                self.db.shortcut = shortcut 
            });
        }
        _loadPosPaymentMethodKey(payment_keys){
            var self = this;
            if (self.db.shortcut){
                self.journal_key = [];
                self.db.journal_key_by_id = {}
                _.each(payment_keys, function(journal){
                    if(self.db.shortcut.payment_methods.includes(journal.id)){
                        self.db.journal_key_by_id[journal.id] = journal;
                        self.journal_key.push(journal)
                    }
                });
            }
        }
    }
    Registries.Model.extend(PosGlobalState, PosOrders);

    const PosResChrome = (Chrome) =>
		class extends Chrome {
            constructor() {
                super(...arguments);
                NumberBufferShortcut.activate();
            }
        };
    Registries.Component.extend(Chrome, PosResChrome);

    const PosResProductScreen = (ProductScreen) =>
		class extends ProductScreen {
            constructor() {
                super(...arguments);
                NumberBufferShortcut.use({
                    triggerAtInput: 'update-page',
                }); 
            }
        }
    Registries.Component.extend(ProductScreen, PosResProductScreen);
});