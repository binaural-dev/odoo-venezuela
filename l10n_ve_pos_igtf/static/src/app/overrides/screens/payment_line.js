import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreenPaymentLines.prototype, {
  getIgtfAmount(paymentline) {
    return this.pos.formatCurrency(paymentline.igtf_amount);
  },
  getForeignIgtfAmount(paymentline) {
    return this.pos.formatForeignCurrency(paymentline.foreign_igtf_amount, true);
  },
});
