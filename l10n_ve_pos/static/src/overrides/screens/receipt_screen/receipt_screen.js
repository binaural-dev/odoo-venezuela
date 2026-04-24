/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup(...arguments);
    },

    get foreignAmount() {
        const order = this.currentOrder;

        if (!order) {
            return 0;
        }
        const foreignAmount = order.amount_total * this.pos.config.foreign_inverse_rate;
        return foreignAmount || 0;
    },

    get l10nVeReceiptData() {
        return {
            foreignAmount: this.foreignAmount,
        };
    },
});