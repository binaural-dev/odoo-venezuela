/** @odoo-module **/

import { Order } from "point_of_sale.models"
import Registries from "point_of_sale.Registries"

const BinauralOrder = (Order) =>
  class BinauralOrder extends Order {
    init_from_JSON(json) {
      super.init_from_JSON(...arguments)
      this.commission_payment_state = json.commission_payment_state
    }
  };

Registries.Model.extend(Order, BinauralOrder);
