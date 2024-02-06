/** @odoo-module **/

import SaleOrderFetcher from "pos_sale.SaleOrderFetcher";
import { patch } from "web.utils";

patch(SaleOrderFetcher, "binaural_subsidiary_pos", {
  async _getOrderIdsForCurrentPage(limit, offset) {
    this.searchDomain = [
      ["subsidiary_id", "=", this.comp.env.pos.config.sh_analytic_account[0]],
    ].concat(this.searchDomain || []);

    return await this._super(limit, offset);
  },
});
