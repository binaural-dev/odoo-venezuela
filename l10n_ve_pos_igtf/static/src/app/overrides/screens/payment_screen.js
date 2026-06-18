/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

// New orders are now associated with the current table, if any.
patch(PaymentScreen.prototype, {

addNewPaymentLine(paymentMethod) {
    let res = super.addNewPaymentLine(...arguments);
    // update_igtf() already called inside Order.add_paymentline()
    // No need to call it again — double invocation causes incorrect
    // last_igtf_amount comparisons and unnecessary recalculation.
    this.render();
    return res
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
