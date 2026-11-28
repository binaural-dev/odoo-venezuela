import { describe, expect, test } from "@odoo/hoot";
import { roundPrecision } from "@web/core/utils/numbers";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import "@l10n_ve_pos/overrides/models/payment_model";
import "@l10n_ve_pos_igtf/app/overrides/models/order_model";
import "@l10n_ve_pos_igtf/app/overrides/models/payment_model";
import { makeCurrency } from "@l10n_ve_pos/../tests/unit/utils";

// Reembolso de una orden con IGTF (tareas 87715 y 87717): devuelve el IGTF de
// la venta, en proporción a lo que reembolsa, con cualquier método de pago.
// Tasa 925,50 Bs/$, IGTF 3 %.

const RATE = 925.5;
const ORIGIN = 7;
const round = (value) => roundPrecision(value, 0.01);
const remainingDue = Object.getOwnPropertyDescriptor(PosOrder.prototype, "remainingDue").get;

function makeRefund(lineAmounts, origin, payments = []) {
    const proto = PosOrder.prototype;
    const total = round(lineAmounts.reduce((sum, amount) => sum + amount, 0));
    const order = {
        isRefund: true,
        to_invoice: true,
        igtf_amount: 0,
        totalDue: total,
        orderIsRounded: false,
        currency: { decimal_places: 2 },
        config: { igtf_percentage: 3 },
        lines: lineAmounts.map((amount) => ({
            priceIncl: amount,
            refunded_orderline_id: { order_id: { id: ORIGIN } },
        })),
        refund_igtf_data: { [ORIGIN]: { id: ORIGIN, ...origin } },
        payment_ids: payments,
        get amountPaid() {
            return round(this.payment_ids.reduce((sum, payment) => sum + payment.amount, 0));
        },
        get_paymentlines() {
            return this.payment_ids;
        },
        get_total_without_igtf: () => total,
        roundLocalMoney: round,
        roundForeignMoney: round,
        localToForeign: (value) => round(value / RATE),
        get_foreign_total_with_tax: () => round(total / RATE),
        _convertOrderAmount: (value) => round(value / RATE),
        _convertForeignOrderAmount: (value) => round(value * RATE),
    };
    for (const name of [
        "_igtfRoundLocal",
        "_igtfToForeign",
        "_igtfBaseState",
        "_igtfRefundShare",
        "_igtfApplyRefundShare",
        "update_igtf",
        "hasRefundIgtf",
        "compute_igtf_amount",
        "get_total_with_igtf",
        "get_foreign_total_with_igtf",
    ]) {
        order[name] = proto[name];
    }
    return order;
}

function makePayment(order, amount, extra = {}) {
    const proto = PosPayment.prototype;
    const payment = {
        pos_order_id: order,
        amount,
        foreign_amount: 0,
        amount_currency: 0,
        igtf_amount: 0,
        foreign_igtf_amount: 0,
        appliesIgtf: false,
        usesAlternateEngine: true,
        currency: makeCurrency(0.01),
        ...extra,
    };
    for (const name of [
        "set_include_igtf",
        "set_igtf_amount",
        "set_foreign_igtf_amount",
        "set_foreign_amount",
        "_localToPaymentCurrency",
        "_paymentCurrencyToLocal",
        "_stampForeignAmount",
        "_recomputeForeignFromLocal",
        "_igtfShownDue",
        "_igtfPanelTotal",
        "_igtfCompare",
        "_igtfGenerates",
    ]) {
        payment[name] = proto[name];
    }
    order.payment_ids.push(payment);
    return payment;
}

describe("l10n_ve_pos_igtf: IGTF de un reembolso", () => {
    test("EUR + Bs: devuelve el IGTF de la venta aunque la línea en Bs vaya primero (tarea 87715)", () => {
        // Venta de 10.000 Bs: 5.036,98 en euros (IGTF 151,11) y el resto, con
        // ese IGTF, en bolívares. Antes, con la línea en Bs primero, la base
        // del IGTF del reembolso quedaba en 4.885,87 y el IGTF en 146,58.
        const order = makeRefund([-6000, -4000], {
            amount_total: 10000,
            igtf_amount: 151.11,
            bi_igtf: 5036.98,
            foreign_igtf_amount: 0.16,
        });
        const bs = makePayment(order, -5114.13);
        const eur = makePayment(order, -5036.98, { appliesIgtf: true });

        order.update_igtf();

        expect(order.igtf_amount).toBe(-151.11);
        expect(order.bi_igtf).toBe(-5036.98);
        expect(order.foreign_igtf_amount).toBe(-0.16);
        expect([eur.include_igtf, eur.igtf_amount, eur.foreign_igtf_amount]).toEqual([true, -151.11, -0.16]);
        expect([Boolean(bs.include_igtf), bs.igtf_amount]).toEqual([false, 0]);
        expect(remainingDue.call(order)).toBe(0);
    });

    test("venta en $ reembolsada en Bs: el reembolso es base + IGTF (tarea 87717)", () => {
        const order = makeRefund([-11043.2], {
            amount_total: 11043.2,
            igtf_amount: 331.3,
            bi_igtf: 11043.2,
            foreign_igtf_amount: 0.36,
        });

        order.update_igtf();

        expect(order.igtf_amount).toBe(-331.3);
        expect(remainingDue.call(order)).toBe(-11374.5);
        expect(order.get_total_with_igtf()).toBe(-11374.5);
        expect(order.get_foreign_total_with_igtf()).toBe(-12.29);
        expect(order.hasRefundIgtf()).toBe(true);

        const bs = makePayment(order, -11043.2);
        order.update_igtf();
        expect(remainingDue.call(order)).toBe(-331.3);

        bs.amount = -11374.5;
        order.update_igtf();
        expect(remainingDue.call(order)).toBe(0);
        expect([bs.include_igtf, bs.igtf_amount, bs.foreign_igtf_amount]).toEqual([true, -331.3, -0.36]);
    });

    test("reembolso parcial: el IGTF en proporción a lo reembolsado", () => {
        const order = makeRefund([-4000], {
            amount_total: 10000,
            igtf_amount: 300,
            bi_igtf: 10000,
            foreign_igtf_amount: 0.32,
        });

        order.update_igtf();

        expect(order.igtf_amount).toBe(-120);
        expect(order.bi_igtf).toBe(-4000);
        expect(order.foreign_igtf_amount).toBe(-0.13);
    });

    test("el último reembolso parcial devuelve el resto exacto del IGTF", () => {
        // 10.000 Bs con IGTF de 300 reembolsados en tres partes: quedan
        // 3.333,34 Bs y 100,01 de IGTF, no el 3 % (100,00).
        const order = makeRefund([-3333.34], {
            amount_total: 3333.34,
            igtf_amount: 100.01,
            bi_igtf: 3333.34,
            foreign_igtf_amount: 0.11,
        });

        order.update_igtf();

        expect(order.igtf_amount).toBe(-100.01);
    });

    test("una venta sin IGTF no devuelve IGTF aunque el reembolso sea en divisa", () => {
        const order = makeRefund([-1000], {
            amount_total: 1000,
            igtf_amount: 0,
            bi_igtf: 0,
            foreign_igtf_amount: 0,
        });
        const usd = makePayment(order, -1000, { appliesIgtf: true });

        order.update_igtf();

        expect(order.igtf_amount).toBe(0);
        expect(Boolean(usd.include_igtf)).toBe(false);
        expect(order.hasRefundIgtf()).toBe(false);
    });

    test("la deuda en $ tecleada después de la línea en Bs salda el reembolso", () => {
        // Antes, la línea en $ valía 5.032,45 Bs (base 4.885,87 + su propio
        // IGTF) y faltaban 4,53 Bs del IGTF de la venta.
        const order = makeRefund([-6000, -4000], {
            amount_total: 10000,
            igtf_amount: 151.11,
            bi_igtf: 5036.98,
            foreign_igtf_amount: 0.16,
        });
        makePayment(order, -5114.13);
        order.update_igtf();
        const usd = makePayment(order, 0, { appliesIgtf: true });

        PosPayment.prototype.set_foreign_amount.call(usd, -5.44);
        order.update_igtf();

        expect(usd.amount).toBe(-5036.98);
        expect(usd.igtf_amount).toBe(-151.11);
        expect(remainingDue.call(order)).toBe(0);
    });

    test("sin el IGTF de la venta el reembolso lo calcula con sus líneas, como antes", () => {
        const order = makeRefund([-1000], {});
        order.refund_igtf_data = undefined;
        makePayment(order, -1000, { appliesIgtf: true });

        order.update_igtf();

        expect(order.igtf_amount).toBe(-30);
    });
});
