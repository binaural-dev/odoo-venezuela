/** @odoo-module **/

import { Order, Orderline, Product, PosGlobalState as Pos } from "point_of_sale.models"
import Registries from "point_of_sale.Registries"

import core from 'web.core';
var _t = core._t;

const BinauralOrderline = (Orderline) =>
  class BinauralOrderline extends Orderline {
    init_from_JSON(json) {
      super.init_from_JSON(...arguments)
      this.pricelist_item = json.pricelist_item_id
    }
    set_unit_price(price) {
      super.set_unit_price(price)
      this.pricelist_item = !!this.product.get_pricelist_item(this.order.pricelist) ? this.product.get_pricelist_item(this.order.pricelist).id : false
    }
    export_as_JSON() {
      let res = super.export_as_JSON()
      res["pricelist_item_id"] = this.pricelist_item
      return res
    }
  };

Registries.Model.extend(Orderline, BinauralOrderline);
