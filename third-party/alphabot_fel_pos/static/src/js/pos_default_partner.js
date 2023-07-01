odoo.define('alphabot_partner_pos.pos', function (require) {
    "use strict";

var { PosGlobalState, Order } = require('point_of_sale.models');
const Registries = require('point_of_sale.Registries');

const alphabotPartnerPosOrder = (Order) => class alphabotPartnerPosOrder extends Order {
    constructor(obj, options) {
        super(...arguments);
//     console.log("*** alphabotPartnerPosOrder constructor");
//        console.log(this.pos.config.alphabot_cliente_id);
        if (this.pos.config.alphabot_cliente_id) {
            var cliente = this.get_partner();
//                console.log(cliente);
            if (!cliente) {
//                console.log("cliente autodefinido");
//                    console.log(cliente);
                this.set_partner(this.pos.db.get_partner_by_id(this.pos.config.alphabot_cliente_id[0]));
            }
            this.to_invoice = true;
        }
//       console.log("*** alphabotPartnerPosOrder fin");
    }
}
Registries.Model.extend(Order, alphabotPartnerPosOrder);

});
