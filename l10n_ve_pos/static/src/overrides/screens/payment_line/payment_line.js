/** @odoo-module */

import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreenPaymentLines.prototype, {
  formatLineAmount(paymentline) {
    // Odoo 19 API: payment_method_id (recordset) + getAmount()
    // Keep backwards-compat with the old snake_case getter our PosPayment
    // patch exposes as an alias.
    const localAmount = typeof paymentline.getAmount === "function"
      ? paymentline.getAmount()
      : (paymentline.amount || 0);
    const foreignAmount = typeof paymentline.get_foreign_amount === "function"
      ? paymentline.get_foreign_amount()
      : (paymentline.foreign_amount || 0);

    const method = paymentline.payment_method_id || paymentline.payment_method;
    const isForeign = Boolean(method?.is_foreign_currency);

    const local = this.env.utils.formatCurrency(localAmount, true);
    const foreign = this.env.utils.formatForeignCurrency(foreignAmount);

    if (paymentline.selected || paymentline.isSelected?.()) {
      return isForeign ? foreign : local;
    }
    return isForeign ? `${foreign} / ${local}` : local;
  },
});
