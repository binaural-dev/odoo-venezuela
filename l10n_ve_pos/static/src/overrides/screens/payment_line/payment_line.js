import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreenPaymentLines.prototype, {
    getFormattedPrice(line) {
        if (line.isForeignPayment) {
            return this.pos.formatCurrency(line.amount_currency, line.currency.id);
        }
        return super.getFormattedPrice(line);
    },
});
