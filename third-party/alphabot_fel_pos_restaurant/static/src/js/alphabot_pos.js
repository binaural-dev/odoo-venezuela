odoo.define('alphabot.POS.Restaurant', function(require) {
    "use strict";

    const { Gui } = require('point_of_sale.Gui');
    var { PosGlobalState, Order } = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');

const alphabotFelPosOrder = (Order) => class alphabotFelPosOrder extends Order {
        export_for_printing() {
            var result = super.export_for_printing(...arguments);
            result.mesa = result.table;
            result.table = false;
            result.customer_count = false;
            return result;
        }
    }

Registries.Model.extend(Order, alphabotFelPosOrder);

});