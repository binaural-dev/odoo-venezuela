/** @odoo-module **/

import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";

// Odoo 19: el core ya maneja el flujo completo de reembolso vía
// TicketScreen.onDoRefund (ver
// point_of_sale/static/src/app/screens/ticket_screen/ticket_screen.js:309).
// Los hooks _getToRefundDetail y _prepareRefundOrderlineOptions de Odoo 17
// ya no existen; el botón "Reembolso total" se reescribe aquí contra la
// API pública actual: getSelectedOrder(), getOrderlines() y
// getToRefundDetail() (todos ya expuestos por el propio TicketScreen).
patch(TicketScreen.prototype, {
  onFullRefund() {
    this.numberBuffer.reset();
    const order = this.getSelectedOrder();
    if (!order) {
      return;
    }
    for (const orderline of order.getOrderlines()) {
      const toRefundDetail = this.getToRefundDetail(orderline);
      // Ya vinculada a una orden de reembolso destino: no tocar su cantidad.
      if (toRefundDetail.destinationOrder) {
        continue;
      }
      const refundableQty = orderline.qty - orderline.refundedQty;
      if (refundableQty <= 0) {
        continue;
      }
      toRefundDetail.qty = refundableQty;
    }
  },
});
