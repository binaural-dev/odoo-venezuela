/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { Component, useRef } from "@odoo/owl";

export class FullRefundButton extends Component {
  static template = "l10n_ve_pos.FullRefundButton";

  setup() {
    this.numberBuffer = useService("number_buffer");
  }
  async click() {
    this.numberBuffer.reset(); // Reset numpad widget values to avoid inconsistency
    const order = this.props.order;
    if (!order) return;
    for (const orderline of order.orderlines) {
      if (!orderline) continue;
      const toRefundDetail =
        this.props.ticket_screen._getToRefundDetail(orderline);
      // When already linked to an order, do not modify the to refund quantity.
      if (toRefundDetail.destinationOrderUid) continue;
      const refundableQty =
        toRefundDetail.orderline.qty - toRefundDetail.orderline.refundedQty;
      if (refundableQty <= 0) continue;
      toRefundDetail.qty = refundableQty;
    }
  }
}
