/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {

  addNewPaymentLine(paymentMethod) {
    let res = super.addNewPaymentLine(...arguments);
    this.currentOrder.update_igtf();
    this.render();
    return res;
  },
  updateSelectedPaymentline(amount = false) {
    super.updateSelectedPaymentline(amount);
    this.currentOrder.update_igtf();
    this.render();
  },

  toggleIsToInvoice() {
    super.toggleIsToInvoice();
    this.currentOrder.update_igtf();
    this.render();
  },
  deletePaymentLine(uuid) {
    super.deletePaymentLine(uuid);
    this.currentOrder.update_igtf();
    this.render();
  },
})
