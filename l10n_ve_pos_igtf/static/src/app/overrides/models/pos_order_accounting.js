/** @odoo-module */
import { PosOrderAccounting } from "@point_of_sale/app/models/accounting/pos_order_accounting";
import { patch } from "@web/core/utils/patch";

patch(PosOrderAccounting.prototype, {

    setup(){
        super.setup();
    },

    _toNumber(value, fallback = 0) {
        const numeric = Number(value);
        return Number.isFinite(numeric) ? numeric : fallback;
    },

    _hasIgtfPaymentLine() {
        const order = this._getOrder();
        const lines = this._getPaymentLines(order);

        return lines.some((line) => {
            const method =
                typeof order?._get_payment_method_data === "function"
                    ? order._get_payment_method_data(line)
                    : line?.payment_method_id;
            return Boolean(method?.apply_igtf);
        });
    },

    _isIgtfContext() {
        const order = this._getOrder();
        if (!order) {
            return false;
        }

        if (this._hasIgtfPaymentLine()) {
            return true;
        }

        const totalDue =
            typeof order.totalDue === "function"
                ? this._toNumber(order.totalDue(), 0)
                : this._toNumber(order.total_due, 0);
        const baseTotal =
            typeof order.get_total_with_tax === "function"
                ? this._toNumber(order.get_total_with_tax(), 0)
                : this._toNumber(order.total_with_tax, 0);

        return Math.abs(totalDue - baseTotal) > 0.000001;
    },

    _getPaymentLines(order = this._getOrder()) {
        const orderLines =
            (typeof order?._get_order_payment_lines === "function" &&
                order._get_order_payment_lines()) ||
            order?.get_paymentlines?.() ||
            order?.paymentlines?.models ||
            order?.paymentlines ||
            order?.payment_ids ||
            order?.payment_lines ||
            [];

        if (Array.isArray(orderLines) && orderLines.length) {
            return orderLines;
        }

        const accountingLines =
            this.paymentlines?.models ||
            this.paymentlines ||
            this.payment_ids ||
            this.payment_lines ||
            [];

        return Array.isArray(accountingLines) ? accountingLines : [];
    },

    get totalDue() {
        const value = super.totalDue;
        console.log("totalDue recalculado", value);
        return value;
    },

    get amountPaid() {
        return this._toNumber(super.amountPaid, 0);
    },


    get remainingDue() {
        return this._toNumber(super.remainingDue, 0);
    },

    isPaid() {
        return Boolean(super.isPaid?.(...arguments));
    },
});
