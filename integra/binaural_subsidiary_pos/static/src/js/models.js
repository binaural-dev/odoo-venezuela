/** @odoo-module **/

import { Order } from "point_of_sale.models";
import Registries from "point_of_sale.Registries";

const BinauralSubsidiaryOrderState = (Order) =>
  class BinauralSubsidiaryOrderState extends Order {
    init_from_JSON(json) {
      super.init_from_JSON(...arguments);
      this.sh_pos_order_analytic_account =
        json["sh_pos_order_analytic_account"];
    }
  };
Registries.Model.extend(Order, BinauralSubsidiaryOrderState);
return BinauralSubsidiaryOrderState;
