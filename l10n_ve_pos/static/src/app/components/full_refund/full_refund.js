/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";
import { Component, useRef } from "@odoo/owl";

export class FullRefundButton extends Component {
  static template = "l10n_ve_pos.FullRefundButton";

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
    if (!order) return;
    for (const orderline of order.orderlines) {
      if (!orderline) continue;
      const toRefundDetail = this.props.ticket_screen.getToRefundDetail(orderline);
      if (toRefundDetail.destination_order_uuid) continue;
      const refundableQty = toRefundDetail.maxQty;
      if (refundableQty <= 0) continue;
      toRefundDetail.qty = refundableQty;
    }
  }
}
