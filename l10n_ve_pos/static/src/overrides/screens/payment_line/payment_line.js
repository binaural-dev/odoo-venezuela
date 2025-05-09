/** @odoo-module */

import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { patch } from "@web/core/utils/patch";

// New orders are now associated with the current table, if any.
patch(PaymentScreenPaymentLines.prototype, {
  formatLineAmount(paymentline) {
    let amount = this.env.utils.formatCurrency(paymentline.get_amount(), true)
    let foreign_amount = this.env.utils.formatForeignCurrency(paymentline.get_foreign_amount())
    if (paymentline.selected) {
      if (paymentline.payment_method.is_foreign_currency) {
        return foreign_amount
      } else {
        return amount
      }
    }
    if (paymentline.payment_method.is_foreign_currency) {
      return foreign_amount + " / " + amount
    } else {
      return foreign_amount + " / " + amount
    }
  }
})
