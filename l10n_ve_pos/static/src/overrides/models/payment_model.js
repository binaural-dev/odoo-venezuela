// /** @odoo-module */

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";

patch(PosPayment.prototype, {
    setup(_defaultObj, options) {
        super.setup(...arguments);

    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.foreign_amount = json.foreign_amount ?? this.foreign_amount;
        this.foreign_rate = json.foreign_rate ?? this.foreign_rate;
    },

    export_as_JSON() {
        let res = super.export_as_JSON(...arguments);
        res["foreign_amount"] = this.foreign_amount;
        res["foreign_rate"] = this.order.get_conversion_rate();
        return res;
    },

    _get_foreign_rate_values() {
        const currentOrder =
            this.order ||
            this.pos?.get_order?.() ||
            this.pos?.getOrder?.() ||
            null;

        const config = currentOrder?.config || this.pos?.config || this.env?.pos?.config || {};
        
        let directRate =
            this.pos?.foreign_currency?.rate ||
            currentOrder?.get_display_rate?.() ||
            currentOrder?.get_conversion_rate?.() ||
            config.foreign_rate ||
            this.foreign_rate ||
            0;

        let inverseRate =
            this.pos?.foreign_currency?.inverse_rate ||
            currentOrder?.get_foreign_inverse_rate?.() ||
            config.foreign_inverse_rate ||
            0;

        if ((!directRate || directRate <= 0) && inverseRate > 0) {
            directRate = 1 / inverseRate;
        }
        if ((!inverseRate || inverseRate <= 0) && directRate > 0) {
            inverseRate = 1 / directRate;
        }
        console.log('Calculated foreign rates', { directRate, inverseRate });
        return { directRate: directRate || 0, inverseRate: inverseRate || 0 };
    },

    get_foreign_amount() {
        const amount = this.amount || 0;
        const paymentMethod = this.payment_method || this.payment_method_id;
        const isForeignMethod = Boolean(paymentMethod?.is_foreign_currency);
        const { directRate, inverseRate } = this._get_foreign_rate_values();
        console.log('Calculating foreign amount', { amount, isForeignMethod, directRate, inverseRate });
        if (directRate && directRate > 0) {
            return amount / directRate;
        }

        if (inverseRate && inverseRate > 0) {
            return amount * inverseRate;
        }

        if (!isForeignMethod && this.order?.init_conversion_rate > 0) {
            return amount / this.order.init_conversion_rate;
        }

        return amount;
    },

    set_amount(amount, only = false) {
        let is_due = amount == this.order.get_due();
        let res = super.set_amount(...arguments);
        if (!only) {
            if (is_due) {
                this.set_foreign_amount(this.order.get_foreign_due(), true);
                return res;
            }
            this.foreign_amount = this.get_foreign_amount();
        }
        return res;
    },

    set_foreign_amount(amount, only = false) {
        this.foreign_amount = amount;
        const paymentMethod = this.payment_method || this.payment_method_id;
        const isForeignMethod = Boolean(paymentMethod?.is_foreign_currency);
        const { directRate, inverseRate } = this._get_foreign_rate_values();

        if (!only) {
            if (this.pos?.currency?.name == "VEF") {
                if (isForeignMethod) {
                    this.amount = directRate > 0 ? this.foreign_amount / directRate : this.foreign_amount;
                    return;
                }
                this.amount = amount / this.order.get_conversion_rate();
            }
            if (this.pos?.currency?.name == "USD") {
                if (isForeignMethod) {
                    this.set_amount(
                        inverseRate > 0 ? this.foreign_amount * inverseRate : this.foreign_amount,
                    );
                    return;
                }
                this.set_amount(
                    this.foreign_amount * this.order.init_conversion_rate,
                    true,
                );
            }
        }
    },
});
