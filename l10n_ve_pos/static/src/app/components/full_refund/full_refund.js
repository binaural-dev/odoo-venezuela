/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

export class FullRefundButton extends Component {
  static template = "l10n_ve_pos.FullRefundButton";
  static props = {
    order: { type: Object, optional: true },
    ticket_screen: { type: Object },
  };

  /**
   * Component setup.
   * Initializes services and hooks used in the component.
   */
  setup() {
    this.numberBuffer = useService("number_buffer");
  }
  /**
   * Click handler for the full refund button.
   * Resets the number buffer and sets the quantity to refund for all lines in the order,
   * if they haven't been linked to a refund order yet and have refundable quantities.
   */
  async click() {
    this.numberBuffer.reset();
    const order = this.props.order;
    const ticketScreen = this.props.ticket_screen;
    if (!order || !ticketScreen) {
      return;
    }

    const orderlines = order.getOrderlines?.() || order.lines || [];
    for (const orderline of orderlines) {
      if (!orderline) continue;
      const toRefundDetail = ticketScreen.getToRefundDetail(orderline);
      if (toRefundDetail.destinationOrder) continue;
      const line = toRefundDetail.line;
      const refundableQty = line ? (line.qty || 0) - (line.refundedQty || 0) : 0;
      if (refundableQty <= 0) continue;
      toRefundDetail.qty = refundableQty;
    }
  }
}
