/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";
import { FullRefundButton } from "@binaural_pos/app/components/full_refund/full_refund";

patch(TicketScreen, {
  components: {
    ...TicketScreen.components,
    FullRefundButton
  },
});

patch(TicketScreen.prototype, {

  async addAdditionalRefundInfo(order, destinationOrder) {
    destinationOrder.to_receipt = order.to_receipt;
    return Promise.resolve();
  },

  _getToRefundDetail(orderline) {
    let res = super._getToRefundDetail(...arguments);
    const { toRefundLines } = this.pos;
    if (orderline.id in toRefundLines) {
      res["orderline"]["foreign_price"] = orderline.foreign_price;
      res["orderline"]["foreign_currency_rate"] = orderline.foreign_currency_rate;
      res["total_with_tax"] = orderline.order.get_total_with_tax();
      res["foreign_total_with_tax"] = orderline.order.get_foreign_total_with_tax();
      return res;
    }
  },
  _prepareRefundOrderlineOptions(toRefundDetail) {
    let res = super._prepareRefundOrderlineOptions(...arguments);
    let { orderline } = toRefundDetail;
    res["foreign_currency_rate"] = orderline.foreign_currency_rate
    res["foreign_price"] = orderline.foreign_price;
    return res
  }
});
