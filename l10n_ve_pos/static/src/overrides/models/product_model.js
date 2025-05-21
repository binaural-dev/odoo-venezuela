/** @odoo-module */

import { Product } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

// New orders are now associated with the current table, if any.
patch(Product.prototype, {
  setup(){
    super.setup(...arguments);
    this.originalTaxes = this.taxes_id
  },
  get_foreign_price(pricelist, quantity, price_extra = 0, recurring = false) {
    let price = super.get_price(...arguments);
    if (this.pos.foreign_currency) {
      price = price * this.pos.get_order().get_conversion_rate();
    }
    return price;
  }
});
