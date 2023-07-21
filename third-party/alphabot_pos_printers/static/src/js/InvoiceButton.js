odoo.define('alphabot_pos_printers.AlphabotInvoiceButton', function (require) {
    'use strict';

    const InvoiceButton = require('point_of_sale.InvoiceButton');
    const Registries = require('point_of_sale.Registries');

    const AlphabotInvoiceButton = InvoiceButton => class extends InvoiceButton {
        async _onClick() {
            const order = this.env.pos.get_order();
            if (order.hasChangesToPrint()) {
                const isPrintSuccessful = await order.printChanges();
                if (isPrintSuccessful) {
                    order.updatePrintedResume();
                }
            }
            await super._onClick();
        }
    };

    Registries.Component.extend(InvoiceButton, AlphabotInvoiceButton);

    return InvoiceButton;
});

