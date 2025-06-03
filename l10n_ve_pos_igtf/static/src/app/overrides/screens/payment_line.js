/** @odoo-module */

import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreenPaymentLines.prototype, {
  formatIgtfAmount(paymentline) {
    let igtf_amount = this.env.utils.formatCurrency(paymentline.igtf_amount, true)
    let foreign_igtf_amount = this.env.utils.formatForeignCurrency(paymentline.foreign_igtf_amount, true)
    return igtf_amount + " / " + foreign_igtf_amount
  }
})
