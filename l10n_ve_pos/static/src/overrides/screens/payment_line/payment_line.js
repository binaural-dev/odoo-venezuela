
import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { patch } from "@web/core/utils/patch";

// New orders are now associated with the current table, if any.
patch(PaymentScreenPaymentLines.prototype, {
  formatLineAmount(paymentline) {
    let foreignAmount = paymentline.get_foreign_amount();
    const isForeignCurrency = paymentline.payment_method_id?.is_foreign_currency;

    if (isForeignCurrency) {
      // Ya no se usa directamente, el input está en el XML
      return `${this.env.utils.formatForeignCurrency(foreignAmount)} / ${this.env.utils.formatCurrency(paymentline.amount)}`;
    }
    return `${this.env.utils.formatCurrency(paymentline.amount)} / ${this.env.utils.formatForeignCurrency(foreignAmount)}`;
  },
})