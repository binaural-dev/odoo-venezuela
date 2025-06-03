/** @odoo-module */

import { PosDB } from "@point_of_sale/app/store/db";
import { patch } from "@web/core/utils/patch";

patch(PosDB.prototype, {
  add_products(products) {
    if (!(products instanceof Array)) {
      products = [products];
    }
    for (var i = 0, len = products.length; i < len; i++) {
      var product = products[i];
      if (product.id in this.product_by_id) {
        this.product_by_id[product.id] = product;
        continue;
      }
    }
    return super.add_products(...arguments);
  }
}) 
