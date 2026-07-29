/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreen.prototype, {

  async addNewPaymentLine(paymentMethod) {
    // Sin caso especial para apply_igtf: la precarga es remainingDue (deuda
    // de factura + deuda IGTF acumulada) y la maneja l10n_ve_pos, que además
    // formatea el numberBuffer con locale. El IGTF que genere esta línea nace
    // en update_igtf() como nuevo restante (diseño 2026-07-09). El clamp
    // IGTF-aware de set_foreign_amount (payment_model.js) evita el drift.
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
