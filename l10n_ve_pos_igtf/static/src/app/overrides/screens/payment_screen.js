/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {

  async addNewPaymentLine(paymentMethod) {
    const order = this.currentOrder;

    // For apply_igtf methods, l10n_ve_pos would convert remainingDue to
    // foreign and call set_foreign_amount, which overwrites line.amount via
    // foreignToLocal → FX rounding drift, and knows nothing about the IGTF
    // surcharge. Our patched order.addPaymentline already leaves the exact
    // closing amount (base + IGTF debt + new IGTF) in local currency, so we
    // bypass l10n_ve_pos entirely and only format the number buffer here.
    if (order?.to_invoice && paymentMethod?.apply_igtf) {
      if (this.paymentLines.length === 0) this.makeAnimation();
      const result = order.addPaymentline(paymentMethod);
      order.update_igtf();
      if (result.status) {
        const line = result.data;
        // Locale-aware formatting: never String()/toFixed(), es_VE parses
        // "." as thousands separator (see l10n_ve_pos payment_screen).
        this.numberBuffer.set(
          paymentMethod.is_foreign_currency
            ? this.env.utils.formatForeignCurrency(line.get_foreign_amount(), false)
            : this.env.utils.formatCurrency(line.getAmount(), false)
        );
      }
      this.render();
      return result.status ? true : false;
    }

    let res = await super.addNewPaymentLine(...arguments);
    this.currentOrder.update_igtf();
    this.render();
    return res;
  },
  updateSelectedPaymentline(amount = false) {
    super.updateSelectedPaymentline(amount);
    this.currentOrder.update_igtf()
    this.render();
  },

  toggleIsToInvoice() {
    super.toggleIsToInvoice()
    this.currentOrder.update_igtf();
    this.render();
  },
  deletePaymentLine(uuid) {
    super.deletePaymentLine(uuid);
    this.currentOrder.update_igtf();
    this.render();
  },
})
