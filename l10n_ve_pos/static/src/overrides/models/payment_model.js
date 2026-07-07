/** @odoo-module */

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";

patch(PosPayment.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.foreign_amount = vals.foreign_amount || 0;
        this.foreign_rate = vals.foreign_rate || 0;
    },

    serializeForORM(opts = {}) {
        const data = super.serializeForORM(opts);
        data["foreign_amount"] = this.foreign_amount || 0;
        data["foreign_rate"] = this.pos_order_id?.init_conversion_rate || 0;
        return data;
    },

    get_foreign_amount() {
        return this.foreign_amount || 0;
    },

    set_foreign_amount(amount) {
        this.foreign_amount = amount;
        const rate = this.pos_order_id?.init_conversion_rate;
        if (rate && rate > 0) {
            this.amount = this.pos_order_id.currency.round(amount * rate);
        } else {
            this.amount = 0;
        }
    },
});
