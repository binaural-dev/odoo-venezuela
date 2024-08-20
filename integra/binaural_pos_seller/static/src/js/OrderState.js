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
            init_from_JSON(json){
              super.init_from_JSON(...arguments)
              this.seller_id = json.seller_id ? json.seller_id : false
            }
            export_as_JSON() {
                let json = super.export_as_JSON();
                json["seller_id"] = this.seller_id ? this.seller_id.id : false;
                return json;
            }
            get rate_from_lines() {
                let rate = super.rate_from_lines

                Object.values(this.pos.toRefundLines).forEach(el => {
                  console.log("EL",el)
                  if(el.seller_id){
                    this.set_seller(el.seller_id)
                  }
                })
                if (this.pos.config.use_seller_from_order != "from_order"){
                  return rate
                }
                let seller = false
                let seller_id = false
                if(!!this.seller_id){
                  return rate
                }
                if(this.get_orderlines().length > 0 && !!this.get_orderlines()[0].sale_order_origin_id){
                  seller_id = this.get_orderlines()[0].sale_order_origin_id.seller_id
                  if (!!seller_id){
                    seller = this.pos.sellers.filter((employee) => employee.id == seller_id[0])
                  }
                }
                if (seller.length > 0){
                  this.set_seller(seller[0])
                }
                return rate
            }
    
        };
    Registries.Model.extend(Order, BinauralOrderStateSeller);
    return BinauralOrderStateSeller;
})
