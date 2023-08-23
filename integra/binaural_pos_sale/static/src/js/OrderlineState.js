odoo.define("binaural_pos_sale.OrderlineState", function(require) {
  "use strict";

  const { Orderline } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");

  const BinauralOrderline = (Orderline) =>
    class BinauralOrderline extends Orderline {
      setQuantityFromSOL(saleOrderLine) {
        this.set_quantity(saleOrderLine.product_uom_qty - Math.max(saleOrderLine.qty_delivered, saleOrderLine.qty_invoiced));
      }
    };
  Registries.Model.extend(Orderline, BinauralOrderline);
})
