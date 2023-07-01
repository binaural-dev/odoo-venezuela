odoo.define('alphabot_fel_pos.PrintBillButton', function(require) {
    'use strict';

    const PrintBillButton = require('pos_restaurant.PrintBillButton');
    const Registries = require('point_of_sale.Registries');

    const AlphabotPrintBillButton = PrintBillButton => class extends PrintBillButton {
        async onClick() {
            const order = this.env.pos.get_order();
            if (!order) return;
            var _alphabot_FEL_Doc = false;
            if(order.change == 0)
            {
                order.change = false;
            }
            order.set_alphabot_FEL_Doc(_alphabot_FEL_Doc);

            if (order.get_orderlines().length > 0) {
                this.trigger('close-popup');
                await this.showScreen('ReprintReceiptScreen', { order: order });
            } else {
                await this.showPopup('ErrorPopup', {
                    title: this.env._t('Nothing to Print'),
                    body: this.env._t('There are no order lines'),
                });
            }
        }
    };

     Registries.Component.extend(PrintBillButton, AlphabotPrintBillButton);

     return AlphabotPrintBillButton;
 });
