odoo.define("binaural_pos_seller.OrderState", function(require) {
    "use strict";

    const { Order, Payment } = require("point_of_sale.models");
    const Registries = require("point_of_sale.Registries");
    const utils = require("web.utils");  

    var round_pr = utils.round_precision;

    const BinauralOrderStateSeller = (Order) =>
        class BinauralOrderStateSeller extends Order {
            constructor(data, opt) {
                super(...arguments);

                this.seller_id = false;
            }
            set_seller(seller){
            this.assert_editable();
            this.seller_id = seller;
            }
            get_seller(){
                return this.seller_id;
            }
            get_seller_name(){
                let seller = this.seller_id;
                return seller ? seller.name : "";
            }

            export_as_JSON() {
                let json = super.export_as_JSON();
                json["seller_id"] = this.seller_id.id;
                return json;
            }
    
        };
    Registries.Model.extend(Order, BinauralOrderStateSeller);
    return BinauralOrderStateSeller;
})
