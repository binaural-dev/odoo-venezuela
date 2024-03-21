/** @odoo-module **/

import SaleOrderFetcher from "pos_sale.SaleOrderFetcher";
import { patch } from "web.utils";

patch(SaleOrderFetcher, "binaural_pos_sale", {
  async _getOrderIdsForCurrentPage(limit, offset) {
    let domain = [['currency_id', '=', this.comp.env.pos.currency.id]].concat(this.searchDomain || []);
    const saleOrders = await this.rpc({
      model: 'sale.order',
      method: 'search_read',
      args: [domain, this.searchFields, offset, limit],
      context: this.comp.env.session.user_context,
    });

    return saleOrders;
  },
  get searchFields() {
    return ['name', 'partner_id', 'amount_total', 'date_order', 'state', 'user_id', 'amount_unpaid'];
  }
});
