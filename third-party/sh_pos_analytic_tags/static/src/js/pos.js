odoo.define('sh_pos_analytic.pos', function (require) {
    'use strict';

    const { PosGlobalState, Order, Orderline, Payment } = require('point_of_sale.models');
    const Registries = require('point_of_sale.Registries');
    var PosDB = require('point_of_sale.DB');
    const PaymentScreen = require("point_of_sale.PaymentScreen");

    const shPosOrder = (Order) => class shPosOrder extends Order {
        export_as_JSON() {
            const json = super.export_as_JSON(...arguments);

            console.log("this.pos.pos_session.sh_analytic_account", this.pos.config)
            json.sh_pos_order_analytic_account = this.pos.config.sh_analytic_account[0] || null;
            return json;
        }
    }
    const shPosOrderLine = (Orderline) => class shPosOrderLine extends Orderline {
        export_as_JSON() {
            const json = super.export_as_JSON(...arguments);
            json.sh_pos_order_analytic_account = this.pos.config.sh_analytic_account[0] || null;
            return json;
        }
    }
    Registries.Model.extend(Order, shPosOrder);
    Registries.Model.extend(Orderline, shPosOrderLine);


    const shPaymentline = (Payment) => class shPaymentline extends Payment {
        export_as_JSON() {
            const json = super.export_as_JSON(...arguments);
            json.sh_analytic_account = this.pos.config.sh_analytic_account[0] || null;
            return json;
        }
    }
    Registries.Model.extend(Payment, shPaymentline);

});