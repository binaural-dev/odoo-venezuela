/** @odoo-module **/

import SaleOrderFetcher from "pos_sale.SaleOrderFetcher";
import { patch } from "web.utils";

patch(SaleOrderFetcher, "binaural_pos_mobile", {
  get searchFields() {
    let res = this._super();
    res.push('tax_included');
    return res
  }
});
