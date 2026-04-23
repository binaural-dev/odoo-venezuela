// /** @odoo-module */

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";

patch(PosPayment.prototype, {
    setup(_defaultObj, options) {
        super.setup(...arguments);
        if (!Number.isFinite(this.foreign_amount)) {
            this.foreign_amount = 0;
        }
    },

    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.foreign_amount = json.foreign_amount ?? this.foreign_amount;
        this.foreign_rate = json.foreign_rate ?? this.foreign_rate;
    },

    export_as_JSON() {
        this._recompute_foreign_amount();
        let res = super.export_as_JSON(...arguments);
        res["foreign_amount"] = this.foreign_amount;
        const { directRate } = this._get_foreign_rate_values();
        res["foreign_rate"] = directRate || this.order.get_conversion_rate() || 0;
        return res;
    },

    _recompute_foreign_amount() {
        const computed = this.get_foreign_amount?.();
        this.foreign_amount = Number.isFinite(computed) ? computed : 0;
    },

    _convert_order_to_foreign(orderAmount = 0) {
        const amount = Number(orderAmount) || 0;
        const { directRate, inverseRate } = this._get_foreign_rate_values();

        if (directRate > 0) {
            return amount / directRate;
        }
        if (inverseRate > 0) {
            return amount / inverseRate;
        }
        return amount;
    },

    _convert_foreign_to_order(foreignAmount = 0) {
        const amount = Number(foreignAmount) || 0;
        const { directRate, inverseRate } = this._get_foreign_rate_values();

        if (directRate > 0) {
            return amount / directRate;
        }
        if (inverseRate > 0) {
            return amount * inverseRate;
        }
        return amount;
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
        
        return { directRate: directRate || 0, inverseRate: inverseRate || 0 };
    },

    get_foreign_amount() {
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
        
        const amount = this.amount || 0 * (directRate > 0 ? 1 / directRate : 1);
                
        return amount
    },

    set_amount(amount, only = false) {
        let is_due = amount == this.order.get_due();
        let res = super.set_amount(...arguments);
        if (!only) {
            if (is_due) {
                this.set_foreign_amount(this.order.get_foreign_due(), true);
                return res;
            }
            this._recompute_foreign_amount();
        }
        return res;
    },

    set_foreign_amount(amount, only = false) {
        this.foreign_amount = Number.isFinite(amount) ? amount : 0;

        if (!only) {
            const orderAmount = this._convert_foreign_to_order(this.foreign_amount);
            super.set_amount(orderAmount, true);
        }
    },
});
