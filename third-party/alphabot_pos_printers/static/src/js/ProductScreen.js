odoo.define('alphabot_pos_printers.AlphabotProductScreen', function(require) {
    'use strict';

    const ProductScreen = require('point_of_sale.ProductScreen');
    const Registries = require('point_of_sale.Registries');

    const AlphaProductScreen = ProductScreen =>
        class extends ProductScreen {

        async _onClickPay() {
            const order = this.env.pos.get_order();
            if (order.hasChangesToPrint()) {
                const isPrintSuccessful = await order.printChanges();
                if (isPrintSuccessful) {
                    order.updatePrintedResume();
                }
            }
            await super._onClickPay();
        }
    };

    Registries.Component.extend(ProductScreen, AlphaProductScreen);

    return ProductScreen;
});
