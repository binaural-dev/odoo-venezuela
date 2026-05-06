/** @odoo-module */
import { PosOrderAccounting } from "@point_of_sale/app/models/accounting/pos_order_accounting";


import { patch } from "@web/core/utils/patch";

patch(PosOrderAccounting.prototype, {
    // get change() {

    //     const cambioBase = Number(super.change ?? 0);
    //     if (!Number.isFinite(cambioBase)) {
    //         return 0;
    //     }

    //     if (!this?.order?.igtf_percentage && !this?.pos_order?.igtf_percentage) {
    //         return Math.max(0, cambioBase);
    //     }
    //     const order = this.order ?? this.pos_order ?? this;

    //     const paymentLines = order.payment_ids ?? order.paymentlines ?? order.payment_lines ?? [];
    //     const igtfPercentage =
    //         order.igtf_percentage ??
    //         0;

    //     const amountDue =
    //         (typeof order.get_total_with_tax === "function"
    //             ? order.get_total_with_tax()
    //             : order.amount_total ?? order.total ?? 0) +
    //         (typeof order.get_total_igtf === "function"
    //             ? order.get_total_igtf()
    //             : order.amount_igtf ?? 0);

    //     const paidBreakdown = paymentLines.reduce(
    //         (acc, line) => {
    //         const amount = Number(line.amount ?? line.payment_amount ?? 0);
    //         const method = line.payment_method_id ?? line.payment_method ?? {};
    //         const methodHasIgtf =
    //             Boolean(method.apply_igtf);
    //         const lineIgtf =
    //             Number(line.igtf_amount ?? line.amount_igtf ?? 0) ||
    //             (methodHasIgtf ? amount * (Number(igtfPercentage) / 100) : 0);

    //             acc.withoutIgtf += amount;
    //             acc.withIgtf += amount + (methodHasIgtf ? lineIgtf : 0);

    //             return acc;
    //         },
    //         { withoutIgtf: 0, withIgtf: 0 }
    //     );

    //     // Evita sobrecontar IGTF cuando el monto de la linea ya lo incluye.
    //     const paidWithIgtfValidation =
    //         Math.abs(paidBreakdown.withoutIgtf - amountDue) <=
    //         Math.abs(paidBreakdown.withIgtf - amountDue)
    //             ? paidBreakdown.withoutIgtf
    //             : paidBreakdown.withIgtf;

    //     return Math.max(0, paidWithIgtfValidation - amountDue);
    // }
});