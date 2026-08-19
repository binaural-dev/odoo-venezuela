import { test, expect, describe } from "@odoo/hoot";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import "@l10n_ve_pos/overrides/models/payment_model";
import { makeCurrency, makeBareCurrency, makeOrderStub } from "./utils";

// set_foreign_amount decide entre "pago completo" (fija el monto local en la
// deuda exacta, sin viaje Bs→$→Bs) y "pago parcial" (conversión estricta).
// Escenario base: total 3.622,86 Bs, tasa 36,50 → deuda foránea $99,26.

const TOTAL = 3622.86;
const FOREIGN_DUE = 99.26;

function callSetForeignAmount(order, requested) {
    const payment = {
        pos_order_id: order,
        amount: 0,
        foreign_amount: 0,
        payment_method_id: { is_foreign_currency: true },
    };
    PosPayment.prototype.set_foreign_amount.call(payment, requested);
    return payment;
}

describe("l10n_ve_pos set_foreign_amount", () => {
    test("pago exacto fija la deuda local sin ida y vuelta", () => {
        const order = makeOrderStub({ totalDue: TOTAL });
        const payment = callSetForeignAmount(order, FOREIGN_DUE);
        // Estricto sería 99,26 × 36,50 = 3.622,99: 13 céntimos fantasma.
        expect(payment.amount).toBe(TOTAL);
        expect(payment.foreign_amount).toBe(FOREIGN_DUE);
    });

    test("sobrepago real: deuda exacta más excedente convertido", () => {
        const order = makeOrderStub({ totalDue: TOTAL });
        const payment = callSetForeignAmount(order, 110);
        // Excedente 110 − 99,26 = $10,74 → 392,01 Bs.
        expect(payment.amount).toBe(TOTAL + 392.01);
    });

    test("pago parcial usa conversión estricta", () => {
        const order = makeOrderStub({ totalDue: TOTAL });
        const payment = callSetForeignAmount(order, 50);
        expect(payment.amount).toBe(1825);
    });

    test("corto por un céntimo real es parcial, no completo", () => {
        const order = makeOrderStub({ totalDue: TOTAL });
        const payment = callSetForeignAmount(order, 99.25);
        expect(payment.amount).toBe(3622.63);
    });

    test("ruido de flotante por encima no genera sobrepago", () => {
        const order = makeOrderStub({ totalDue: TOTAL });
        const payment = callSetForeignAmount(order, FOREIGN_DUE + 1e-9);
        expect(payment.amount).toBe(TOTAL);
    });

    test("ruido de flotante por debajo sigue siendo pago completo", () => {
        const order = makeOrderStub({ totalDue: TOTAL });
        const payment = callSetForeignAmount(order, FOREIGN_DUE - 1e-9);
        expect(payment.amount).toBe(TOTAL);
    });

    test("deuda cero: conversión estricta (guard isZero)", () => {
        const order = makeOrderStub({ totalDue: 0 });
        const payment = callSetForeignAmount(order, 10);
        expect(payment.amount).toBe(365);
    });

    test("reembolso cubierto fija la deuda local negativa exacta", () => {
        const order = makeOrderStub({ totalDue: -TOTAL });
        const payment = callSetForeignAmount(order, -FOREIGN_DUE);
        expect(payment.amount).toBe(-TOTAL);
    });

    test("reeditar la propia línea no se cuenta a sí misma", () => {
        const other = { isDone: () => true, getAmount: () => 1000 };
        const order = makeOrderStub({ totalDue: TOTAL });
        const payment = {
            pos_order_id: order,
            amount: 0,
            foreign_amount: 0,
            payment_method_id: { is_foreign_currency: true },
        };
        order.payment_ids = [payment, other];
        // Deuda restante 2.622,86 Bs → $71,86. Expected como expresión para
        // igualar bit a bit la resta en flotante que hace el código.
        PosPayment.prototype.set_foreign_amount.call(payment, 71.86);
        expect(payment.amount).toBe(TOTAL - 1000);
    });

    test("moneda sin resolver: rama de respaldo con tolerancia manual", () => {
        const order = makeOrderStub({ totalDue: TOTAL, fc: makeBareCurrency() });
        expect(callSetForeignAmount(order, FOREIGN_DUE).amount).toBe(TOTAL);
        expect(callSetForeignAmount(order, 50).amount).toBe(1825);
    });

    test("orden sin helpers de conversión: monto local 0", () => {
        const payment = {
            pos_order_id: {},
            amount: 99,
            foreign_amount: 0,
            payment_method_id: { is_foreign_currency: true },
        };
        PosPayment.prototype.set_foreign_amount.call(payment, 25);
        expect(payment.amount).toBe(0);
        expect(payment.foreign_amount).toBe(25);
    });
});

// _recomputeForeignFromLocal corre en TODO pago (setAmount), sin importar
// is_foreign_currency: un pago en Bs también necesita su equivalente en USD
// para la contabilidad dual (openspec/migration-lessons.md, "Pendientes por
// tratar (2026-07-10)"). Antes se zereaba a propósito para métodos locales.
describe("l10n_ve_pos _recomputeForeignFromLocal", () => {
    test("método local (Bs): calcula el equivalente foráneo, no lo zerea", () => {
        const order = makeOrderStub({ totalDue: TOTAL });
        const payment = {
            pos_order_id: order,
            amount: TOTAL,
            foreign_amount: 0,
            payment_method_id: { is_foreign_currency: false },
        };
        PosPayment.prototype._recomputeForeignFromLocal.call(payment);
        expect(payment.foreign_amount).toBe(FOREIGN_DUE);
    });

    test("método foráneo: sigue calculando igual que antes", () => {
        const order = makeOrderStub({ totalDue: TOTAL });
        const payment = {
            pos_order_id: order,
            amount: TOTAL,
            foreign_amount: 0,
            payment_method_id: { is_foreign_currency: true },
        };
        PosPayment.prototype._recomputeForeignFromLocal.call(payment);
        expect(payment.foreign_amount).toBe(FOREIGN_DUE);
    });

    test("sin orden o sin localToForeign: cae a 0", () => {
        const payment = {
            pos_order_id: null,
            amount: TOTAL,
            foreign_amount: 99,
            payment_method_id: { is_foreign_currency: false },
        };
        PosPayment.prototype._recomputeForeignFromLocal.call(payment);
        expect(payment.foreign_amount).toBe(0);
    });
});
