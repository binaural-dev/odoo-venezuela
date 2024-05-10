/** @odoo-module **/

import SaleOrderFetcher from "pos_sale.SaleOrderFetcher";
import { patch } from "web.utils";

patch(SaleOrderFetcher, "binaural_pos_seller", {
  get searchFields() {
    let res = this._super(...arguments);
    res.push("seller_id");
    return res
  }
});
