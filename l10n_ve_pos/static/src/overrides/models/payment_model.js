/** @odoo-module */

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";

// Live patch for Odoo 19 PosPayment.
//
// Keeps `foreign_amount` (the display amount in the *foreign* currency) in
// sync with `amount` (the amount in the POS main currency), using the
// conversion helpers exposed by pos.order (which respect the "which one is
// the main currency" business rule).
patch(PosPayment.prototype, {
    setup(vals) {
        super.setup(...arguments);
        this.foreign_amount = vals.foreign_amount || 0;
        this.foreign_rate = vals.foreign_rate || 0;
    },

    serializeForORM(opts = {}) {
        const data = super.serializeForORM(opts);
        data["foreign_amount"] = this.foreign_amount || 0;
        data["foreign_rate"] = Number(this.pos_order_id?.get_foreign_multiplier?.() ?? 0);
        return data;
    },

    _isForeignMethod() {
        return Boolean(this.payment_method_id?.is_foreign_currency);
    },

    _recomputeForeignFromLocal() {
        // Called when the local `amount` is the source of truth (core setAmount).
        // Uses the centralized pos_order._convert (mirror of pos.config._convert).
        if (!this._isForeignMethod()) {
            this.foreign_amount = 0;
            return;
        }
        const order = this.pos_order_id;
        if (!order || typeof order.localToForeign !== "function") {
            this.foreign_amount = 0;
            return;
        }
        this.foreign_amount = order.localToForeign(this.amount || 0);
    },

    setAmount(value) {
        super.setAmount(value);
        this._recomputeForeignFromLocal();
    },

    get_amount() {
        // Odoo 19 renamed to getAmount(); keep get_amount() as an alias
        // because our templates and helpers still use snake_case.
        return this.getAmount();
    },

    get_foreign_amount() {
        return this.foreign_amount || 0;
    },

    set_foreign_amount(amount) {
        // Foreign method: the user typed the foreign amount directly. We
        // need to compute the equivalent LOCAL amount so the core's
        // remainingDue = totalDue - amountPaid works.
        //
        // Business rule (Odoo native behavior for foreign payments): when
        // the foreign amount covers the foreign due of the order, we treat
        // the order as fully settled — the local `amount` is set to exactly
        // the LOCAL remaining due, not the mathematical `foreign / rate`.
        // Difference between them is FX-rounding noise that in real
        // accounting is absorbed by an FX gain/loss entry.
        //
        // If the foreign amount is a partial payment (< foreign due), fall
        // back to strict conversion.
        const order = this.pos_order_id;
        const requested = Number(amount) || 0;
        this.foreign_amount = requested;

        if (!order || typeof order.foreignToLocal !== "function") {
            this.amount = 0;
            return;
        }

        // Foreign due of the order BEFORE this payment line.
        // Sum foreign_amount of every OTHER done payment line and subtract
        // from the foreign total. We exclude self so a re-edit of the same
        // line doesn't cascade.
        const foreignTotal = Number(order.get_foreign_total_with_tax?.() ?? 0) || 0;
        const foreignPaidOthers = Array.from(order.payment_ids || []).reduce((sum, line) => {
            if (line === this) return sum;
            const done = typeof line.isDone === "function" ? line.isDone() : true;
            if (!done) return sum;
            return sum + (Number(line.get_foreign_amount?.() ?? 0) || 0);
        }, 0);
        const foreignDueBefore = Math.max(0, foreignTotal - foreignPaidOthers);
        const foreignCurrency = order.get_foreign_currency?.();
        const foreignRounding = Number(foreignCurrency?.rounding) || 0.01;

        // "Covers the due" means requested >= due, using foreign currency
        // rounding as tolerance (avoids float-noise misclassification).
        const coversDue = (requested + foreignRounding / 2) >= foreignDueBefore
                         && foreignDueBefore > 0;

        if (coversDue) {
            // Local amount = exact local remaining due + any overpayment
            // (overpayment stays as change; core computes it from
            // amountPaid - totalDue).
            //
            // Local remaining due BEFORE this payment line:
            const localTotal = Number(order.totalDue ?? 0) || 0;
            const localPaidOthers = Array.from(order.payment_ids || []).reduce((sum, line) => {
                if (line === this) return sum;
                const done = typeof line.isDone === "function" ? line.isDone() : true;
                if (!done) return sum;
                return sum + (Number(line.getAmount?.() ?? line.amount ?? 0) || 0);
            }, 0);
            const localDueBefore = Math.max(0, localTotal - localPaidOthers);
            const overpaymentForeign = Math.max(0, requested - foreignDueBefore);
            const overpaymentLocal = overpaymentForeign > 0
                ? order.foreignToLocal(overpaymentForeign)
                : 0;
            this.amount = localDueBefore + overpaymentLocal;
            return;
        }

        // Partial payment: strict mathematical conversion.
        this.amount = order.foreignToLocal(requested);
    },
});
