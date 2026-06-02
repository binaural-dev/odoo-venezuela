/** @odoo-module **/

import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";
import { FullRefundButton } from "@l10n_ve_pos/app/components/full_refund/full_refund";

patch(TicketScreen, {
  components: {
    ...TicketScreen.components,
    FullRefundButton,
  },
});

patch(TicketScreen.prototype, {
  async addAdditionalRefundInfo(order, destinationOrder) {
    destinationOrder.to_receipt = order.to_receipt;
    destinationOrder.foreign_currency_rate = order.foreign_currency_rate;
    if (destinationOrder.isRefund) {
      for (const line of destinationOrder.lines) {
        if (line.refunded_orderline_id && line.refunded_orderline_id.foreign_price) {
          line.foreign_price = line.refunded_orderline_id.foreign_price;
        }
      }
    }
  },
});
