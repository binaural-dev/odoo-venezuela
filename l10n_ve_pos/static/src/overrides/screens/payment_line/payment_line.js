
import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { patch } from "@web/core/utils/patch";

// New orders are now associated with the current table, if any.
patch(PaymentScreenPaymentLines.prototype, {
  formatLineAmount(paymentline) {
    let foreignAmount = paymentline.get_foreign_amount()
    console.log("Formatted foreign amount for display:", foreignAmount)
    return this.env.utils.formatForeignCurrency(foreignAmount);
  },
})