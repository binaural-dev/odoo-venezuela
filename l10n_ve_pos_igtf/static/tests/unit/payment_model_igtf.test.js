import { describe, expect, test } from "@odoo/hoot";
import { roundPrecision } from "@web/core/utils/numbers";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import "@l10n_ve_pos/overrides/models/payment_model";
import "@l10n_ve_pos_igtf/app/overrides/models/order_model";
import "@l10n_ve_pos_igtf/app/overrides/models/payment_model";
import { makeCurrency } from "@l10n_ve_pos/../tests/unit/utils";

// Pago en divisa de una orden facturada con IGTF (3 %), tasa 925,50 Bs/$.
// La orden usa el cálculo real de IGTF del módulo (_igtfBaseState,
// compute_igtf_amount y get_foreign_total_with_igtf).

const RATE = 925.5;
const round = (value) => roundPrecision(value, 0.01);

function makeIgtfOrder(total, payments = []) {
    const proto = PosOrder.prototype;
    return {
        to_invoice: true,
        igtf_amount: 0,
        totalDue: total,
        currency: { decimal_places: 2 },
        config: { igtf_percentage: 3 },
        payment_ids: payments,
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
        _igtfRoundLocal: proto._igtfRoundLocal,
        _igtfToForeign: proto._igtfToForeign,
        _igtfBaseState: proto._igtfBaseState,
        compute_igtf_amount: proto.compute_igtf_amount,
        get_foreign_total_with_igtf: proto.get_foreign_total_with_igtf,
    };
}

function makeIgtfPayment(order, extra = {}) {
    const proto = PosPayment.prototype;
    return {
        pos_order_id: order,
        amount: 0,
        foreign_amount: 0,
        amount_currency: 0,
        appliesIgtf: true,
        usesAlternateEngine: true,
        currency: makeCurrency(0.01),
        _localToPaymentCurrency: proto._localToPaymentCurrency,
        _paymentCurrencyToLocal: proto._paymentCurrencyToLocal,
        _stampForeignAmount: proto._stampForeignAmount,
        _recomputeForeignFromLocal: proto._recomputeForeignFromLocal,
        _igtfShownDue: proto._igtfShownDue,
        _igtfPanelTotal: proto._igtfPanelTotal,
        _igtfCompare: proto._igtfCompare,
        ...extra,
    };
}

function pay(order, typed, extra = {}) {
    const payment = makeIgtfPayment(order, extra);
    PosPayment.prototype.set_foreign_amount.call(payment, typed);
    return payment;
}

describe("l10n_ve_pos_igtf set_foreign_amount", () => {
    test("el total con IGTF tecleado en una línea salda la orden exacta (tarea 87707)", () => {
        // 1.000 Bs + 30 Bs de IGTF = 1.030 Bs ($1,11). Antes la línea valía
        // 1.027,77 Bs y quedaba un restante de 2,23 Bs.
        const payment = pay(makeIgtfOrder(1000), 1.11);
        expect(payment.amount).toBe(1030);
        expect(payment.amount_currency).toBe(1.11);
    });

    test("la cifra del panel salda la orden aunque sea un centavo mayor que el total redondeado", () => {
        // 1.079,87 + 32,40 = 1.112,27 Bs: el total redondeado es $1,20, pero el
        // panel suma $1,17 + $0,04 = $1,21.
        const order = makeIgtfOrder(1079.87);
        expect(order.get_foreign_total_with_igtf()).toBe(1.21);
        expect(pay(order, 1.21).amount).toBe(1112.27);
        expect(pay(order, 1.2).amount).toBe(1112.27);
    });

    test("teclear solo la deuda deja el IGTF como nuevo restante (dos líneas)", () => {
        const payment = pay(makeIgtfOrder(11043.2), 11.93);
        expect(payment.amount).toBe(11043.2);
    });

    test("un centavo menos que el total con IGTF no salda la orden", () => {
        // Total con IGTF 11.374,50 Bs ($12,29): $12,28 vale lo entregado.
        const payment = pay(makeIgtfOrder(11043.2), 12.28);
        expect(payment.amount).toBe(11365.14);
    });

    test("sobrepago en dólares: vale lo entregado a la tasa", () => {
        const payment = pay(makeIgtfOrder(11043.2), 12.3);
        expect(payment.amount).toBe(11383.65);
    });

    test("sobrepago en euros: lo entregado por la tasa del euro (tarea 87709)", () => {
        // Datos del ticket: base 11.043,20 Bs, euro a 1.007,3958, 11,30 €
        // entregados. Antes la línea valía 11.385,71 Bs; 11,30 × 1.007,3958 =
        // 11.383,57 Bs.
        const eurRate = 1007.3958;
        const order = {
            ...makeIgtfOrder(11043.2),
            currency: { decimal_places: 2, round, convert: (value) => value },
            convertAmountToCurrency: (value) => round(value / eurRate),
        };
        const eur = { ...makeCurrency(0.01), convertToDefaultCurrency: (value) => value * eurRate };
        const payment = pay(order, 11.3, { usesAlternateEngine: false, currency: eur });
        expect(payment.amount).toBe(11383.57);
        expect(payment.amount_currency).toBe(11.3);
    });
});
