/** @odoo-module **/

import SaleOrderFetcher from "pos_sale.SaleOrderFetcher";
import { patch } from "web.utils";

patch(SaleOrderFetcher, "binaural_pos_website", {
  async _getOrderIdsForCurrentPage(limit, offset) {
    if (!this.comp.env.pos.config.only_website){
      return await this._super(limit, offset);
    }
    this.searchDomain.push(["team_id", '=', this.comp.env.pos.config.team_sale_website_id[0]]);
    return await this._super(limit, offset);
  },
});
