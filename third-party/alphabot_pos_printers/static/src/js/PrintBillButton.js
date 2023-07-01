odoo.define('alphabot_pos_printers.PrintBillButton', function(require) {
    'use strict';

    const PrintBillButton = require('pos_restaurant.PrintBillButton');
    const Registries = require('point_of_sale.Registries');

    const AlphabotPrintBillButton = (PrintBillButton) => class extends PrintBillButton {
        async onClick() {
            const order = this.env.pos.get_order();
            if (order.hasChangesToPrint()) {
                const isPrintSuccessful = await order.printChanges();
                if (isPrintSuccessful) {
                    order.updatePrintedResume();
                };
            };
            await super.onClick();
        };
    };

    Registries.Component.extend(PrintBillButton, AlphabotPrintBillButton);

    return PrintBillButton;
});
