odoo.define("binaural_pos_mobile.OrderState", function(require) {
  "use strict";

  const { Order, Payment } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");
  const utils = require("web.utils");

  var round_pr = utils.round_precision;

  const BinauralOrderState = (Order) =>
    class extends Order {
      get_orderlines() {
        if(!this.cid || !this.pos.get_order()){
          return super.get_orderlines();
        }

        if (this.cid != this.pos.get_order().cid) {
          return super.get_orderlines();
        }

        if (this.orderlines.length < 1) {
          this.lock_toggle_receipt_invoice = false
          return super.get_orderlines();
        }

        let line = this.orderlines[0]

        if (!line.sale_order_origin_id) {
          return  super.get_orderlines();
        }

        this.to_receipt = !line.sale_order_origin_id.tax_included
        this.lock_toggle_receipt_invoice = true

        return super.get_orderlines();
      }
    };
  Registries.Model.extend(Order, BinauralOrderState);
  return BinauralOrderState;
})
