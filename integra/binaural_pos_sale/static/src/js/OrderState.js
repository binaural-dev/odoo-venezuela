/* @odoo-module */

import { Order } from "point_of_sale.models";
import Registries from "point_of_sale.Registries";
import utils from "web.utils";

const BinauralOrderState = (Order) =>
  class BinauralOrderState extends Order {
    get rate_from_lines() {
      let rate = super.rate_from_lines
      if (!this.pos.config.pos_use_rate_from_order){
        return rate
      }
      this.get_orderlines().forEach(line => {
        if(!!line.get_sale_order()){
          rate = line.sale_order_line_id.foreign_inverse_rate
        }
      })
      return rate
    }
  };
Registries.Model.extend(Order, BinauralOrderState);
return BinauralOrderState;
