/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

// New orders are now associated with the current table, if any.
patch(PaymentScreen.prototype, {

  async addNewPaymentLine(paymentMethod) {
    const res = await super.addNewPaymentLine(...arguments);
    const order = this.currentOrder || this.pos.get_order();
    order?.update_igtf();

    this.render();
    return res;
  },
  updateSelectedPaymentline(amount = false) {
    super.updateSelectedPaymentline(amount);
    this.pos.get_order().update_igtf()
    this.render();
  },

  toggleIsToInvoice() {
    super.toggleIsToInvoice()
    this.currentOrder.update_igtf();
    this.render();
  }
})
