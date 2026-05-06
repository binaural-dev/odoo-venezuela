/** @odoo-module */

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";

patch(PosPayment.prototype, {
    setup(options) {
        super.setup(...arguments);
        if (!Number.isFinite(this.foreign_amount)) {
            this.foreign_amount = 0;
        }
    },

    init_from_JSON(json) {
        if (typeof super.init_from_JSON === "function") {
            super.init_from_JSON(...arguments);
        }
        this.foreign_amount = json.foreign_amount ?? this.foreign_amount;
        this.foreign_rate = json.foreign_rate ?? this.foreign_rate;
    },

    export_as_JSON() {
        this._recompute_foreign_amount();
        let res =
            typeof super.export_as_JSON === "function"
                ? super.export_as_JSON(...arguments)
                : typeof super.serializeForORM === "function"
                  ? super.serializeForORM(...arguments)
                  : {};
        const order = this._getCurrentOrder();
        res["foreign_amount"] = this.foreign_amount;
        const { directRate } = this._get_foreign_rate_values();
        res["foreign_rate"] = directRate || order?.get_conversion_rate?.() || 0;
        return res;
    },

    _recompute_foreign_amount() {
        const computed = this.getForeignAmount?.() ?? this.get_foreign_amount?.();
        this.foreign_amount = Number.isFinite(computed) ? computed : 0;
    },

    _getCurrentOrder() {
        return (
            this.pos_order_id ||
            this.order ||
            this.pos?.getOrder?.() ||
            this.pos?.get_order?.() ||
            null
        );
    },

    _getOrderDue() {
        const order = this._getCurrentOrder();
        if (!order) {
            return 0;
        }
        if (typeof order.getDue === "function") {
            return Number(order.getDue()) || 0;
        }
        if (typeof order.get_due === "function") {
            return Number(order.get_due()) || 0;
        }
        return Number(order.remainingDue) || 0;
    },

    _getForeignDue() {
        const order = this._getCurrentOrder();
        if (!order) {
            return 0;
        }
        if (typeof order.getForeignDue === "function") {
            return Number(order.getForeignDue()) || 0;
        }
        if (typeof order.get_foreign_due === "function") {
            return Number(order.get_foreign_due()) || 0;
        }
        return 0;
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
        const currentOrder = this._getCurrentOrder();

        const config = currentOrder?.config || this.pos?.config || this.env?.pos?.config || {};
        
        let directRate =
            this.pos?.foreign_currency?.rate ||
            currentOrder?.get_conversion_rate?.() ||
            config.foreign_rate ||
            currentOrder?.get_display_rate?.() ||
            this.foreign_rate ||
            0;

        let inverseRate =
            this.pos?.foreign_currency?.inverse_rate ||
            config.foreign_inverse_rate ||
            currentOrder?.get_foreign_inverse_rate?.() ||
            0;

        if ((!directRate || directRate <= 0) && inverseRate > 0) {
            directRate = 1 / inverseRate;
        }
        if ((!inverseRate || inverseRate <= 0) && directRate > 0) {
            inverseRate = 1 / directRate;
        }
        
        return { directRate: directRate || 0, inverseRate: inverseRate || 0 };
    },

    getForeignAmount() {
        const currentOrder = this._getCurrentOrder();

        const config = currentOrder?.config || this.pos?.config || this.env?.pos?.config || {};
        
        let directRate =
            this.pos?.foreign_currency?.rate ||
            currentOrder?.get_conversion_rate?.() ||
            config.foreign_rate ||
            currentOrder?.get_display_rate?.() ||
            this.foreign_rate ||
            0;
        
        const amount = (this.amount || 0) * (directRate > 0 ? 1 / directRate : 1);
                
        return amount;
    },

    serializeForORM(opts = {}) {
        this._recompute_foreign_amount();
        const data = super.serializeForORM(opts);
        const { directRate } = this._get_foreign_rate_values();
        const order = this._getCurrentOrder();
        data.foreign_amount = this.foreign_amount;
        data.foreign_rate = directRate || order?.get_conversion_rate?.() || 0;
        return data;
    },

    get_foreign_amount() {
        return this.getForeignAmount();
    },

    setAmount(amount, only = false) {
        const numericAmount = Number(amount) || 0;
        const isDue = Math.abs(numericAmount - this._getOrderDue()) <= 0.000001;
        let res = super.setAmount(...arguments);
        if (!only) {
            if (isDue) {
                this.setForeignAmount(this._getForeignDue(), true);
                return res;
            }
            this._recompute_foreign_amount();
        }
        return res;
    },

    set_amount(amount, only = false) {
        return this.setAmount(amount, only);
    },

    setForeignAmount(amount, only = false) {
        const numericAmount = Number(amount);
        this.foreign_amount = Number.isFinite(numericAmount) ? numericAmount : 0;

        if (!only) {
            const orderAmount = this._convert_foreign_to_order(this.foreign_amount);
            super.setAmount(orderAmount, true);
        }
    },

    set_foreign_amount(amount, only = false) {
        return this.setForeignAmount(amount, only);
    },
});
