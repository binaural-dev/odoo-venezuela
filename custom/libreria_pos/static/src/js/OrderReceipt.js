/** @odoo-module **/

odoo.define("libreria_pos.OrderlineState", function (require) {
    "use strict";

    const { OrderReceipt } = require("point_of_sale.models");
    const Registries = require("point_of_sale.Registries");


    class OrderReceipt extends PosComponent {
        constructor() {
            super(...arguments)
        }

        get_orderline(product_name) {
            console.log("Aaaaaaaaaaaa")
            const orderline = this.env.pos.selectedOrder.orderLines.filter((orderline) => orderline.product.display_name === product_name);
            return orderline[0];
        }

    }

    Registries.Model.extend(OrderReceipt, BinauralOrderline);
})
