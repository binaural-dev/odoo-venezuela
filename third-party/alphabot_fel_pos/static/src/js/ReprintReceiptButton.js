odoo.define('point_of_sale.AlphabotReprintReceiptButton', function (require) {
    'use strict';

    const ReprintReceiptButton = require('point_of_sale.ReprintReceiptButton');
    const Registries = require('point_of_sale.Registries');

    const AlphabotReprintReceiptButton = ReprintReceiptButton => class extends ReprintReceiptButton {
        async _onClick() {
            console.log("*** AlphabotReprintReceiptButton");
            const order = this.props.order;
            if (!order) return;
            var _alphabot_FEL_Doc = false;
            if(order.change == 0)
            {
                order.change = false;
            }
            order.set_alphabot_FEL_Doc(_alphabot_FEL_Doc);
            this.showScreen('ReprintReceiptScreen', { order: order });
        }
    };

    Registries.Component.extend(ReprintReceiptButton, AlphabotReprintReceiptButton);

    return AlphabotReprintReceiptButton;
});
