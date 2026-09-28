import { test, expect, describe } from "@odoo/hoot";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import "@l10n_ve_pos/overrides/models/pos_order";
import { makeCurrency } from "./utils";

// Decimal-precision tests for the REAL conversion engine
// (_getPosConversionRate/_convert/localToForeign/foreignToLocal) in
// static/src/overrides/models/pos_order.js.
//
// Why this file exists: the only existing coverage that touches these
// names (payment_model.test.js, payment_screen.test.js) runs against
// `utils.js::makeOrderStub`, a HAND-WRITTEN stub that reimplements
// localToForeign/foreignToLocal with a fixed toy rate
// (`v / RATE`/`v * RATE`) — it never calls the real prototype methods.
// The direction-selection logic that actually matters here (which of
// `foreign_rate`/`foreign_inverse_rate` applies to which direction, the
// same-currency shortcut, the no-rate fallback, `doRound=false`) has NO
// test anywhere. This mirrors, on the JS side, the same "distintas tasas
// y configuraciones, ejecutando _convert debe dar lo mismo" precision
// sweep already done on the Python side
// (`l10n_ve_pos/tests/test_pos_config_convert_precision.py`).
//
// Object.create(PosOrder.prototype) + Object.defineProperty: same pattern
// as pos_order_rounding.test.js — the prototype has getter-only
// properties (`config`, `currency`) with no setter, so a plain object
// literal / Object.assign would throw under strict mode.
function makeOrderThis(props = {}) {
    const order = Object.create(PosOrder.prototype);
    for (const [key, value] of Object.entries(props)) {
        Object.defineProperty(order, key, { value, configurable: true, writable: true });
    }
    return order;
}

function makeCurrencyWithId(id, rounding = 0.01) {
    return { id, ...makeCurrency(rounding) };
}

// Role assignment: main = USD (id 1), foreign = VEF (id 2) — same as the
// Python precision suite's ``config_usd_main``. ``bsPerUsd`` means
// "1 USD = bsPerUsd VEF": main(USD)→foreign(VEF) must then multiply by
// ``bsPerUsd`` directly (that is what ``foreign_inverse_rate`` carries in
// this role assignment — see the source file's own worked example, which
// uses the OPPOSITE role assignment and therefore the opposite magnitude
// naming; the direction rule, not the CHICO/GRANDE label, is what's
// invariant), and foreign(VEF)→main(USD) by its reciprocal
// (``foreign_rate``).
function makeOrderWithRate(bsPerUsd, { mainId = 1, foreignId = 2 } = {}) {
    const main = makeCurrencyWithId(mainId, 0.01);
    const foreign = makeCurrencyWithId(foreignId, 0.01);
    const order = makeOrderThis({
        currency: main,
        config: {
            foreign_currency_id: foreign,
            foreign_inverse_rate: bsPerUsd,
            foreign_rate: 1 / bsPerUsd,
        },
    });
    return { order, main, foreign };
}

// Deliberately "ugly" (many-decimal) rates — a real BCV rate is never a
// round number, and a round one would hide float/rounding bugs.
const BS_PER_USD_RATES = [
    0.99999949, // near 1:1
    36.567891234, // realistic
    189.34567891234, // realistic, more decimals
    7654321.123456, // hyperinflation-scale
];
const AMOUNTS = [0.01, 1, 33.33, 100, 999999.99];

describe("l10n_ve_pos _getPosConversionRate", () => {
    test("main→foreign usa foreign_inverse_rate, foreign→main usa foreign_rate", () => {
        const { order, main, foreign } = makeOrderWithRate(36.5);
        expect(order._getPosConversionRate(main, foreign)).toBe(36.5);
        expect(order._getPosConversionRate(foreign, main)).toBe(1 / 36.5);
    });

    test("misma moneda → 1, sin mirar la config", () => {
        const { order, main } = makeOrderWithRate(36.5);
        // config vacía a propósito: si esta rama mirara foreign_rate,
        // devolvería 0 en vez de 1.
        const bare = makeOrderThis({ config: {} });
        expect(bare._getPosConversionRate(main, main)).toBe(1);
    });

    test("sin foreign_currency_id configurada → 0", () => {
        const order = makeOrderThis({ config: {} });
        const cur = makeCurrencyWithId(1);
        const other = makeCurrencyWithId(2);
        expect(order._getPosConversionRate(cur, other)).toBe(0);
    });

    test("dirección que no involucra la moneda foránea → 0", () => {
        const { order } = makeOrderWithRate(36.5);
        const thirdCurrency = makeCurrencyWithId(3);
        const fourthCurrency = makeCurrencyWithId(4);
        expect(order._getPosConversionRate(thirdCurrency, fourthCurrency)).toBe(0);
    });

    test("tasa configurada en 0 o negativa → 0, nunca NaN ni negativa", () => {
        const { order, main, foreign } = makeOrderWithRate(36.5);
        order.config.foreign_inverse_rate = 0;
        expect(order._getPosConversionRate(main, foreign)).toBe(0);
        order.config.foreign_inverse_rate = -5;
        expect(order._getPosConversionRate(main, foreign)).toBe(0);
    });
});

describe("l10n_ve_pos _convert — precisión decimal con distintas tasas", () => {
    test("multiplica por la tasa cruda y redondea SOLO el resultado final", () => {
        for (const bsPerUsd of BS_PER_USD_RATES) {
            const { order, main, foreign } = makeOrderWithRate(bsPerUsd);
            for (const [from, to] of [
                [main, foreign],
                [foreign, main],
            ]) {
                const rawRate = order._getPosConversionRate(from, to);
                expect(rawRate).not.toBe(0);
                for (const amount of AMOUNTS) {
                    const converted = order._convert(amount, from, to);
                    const expected = to.round(amount * rawRate);
                    expect(converted).toBe(expected);

                    // La tasa nunca se redondea antes de multiplicar:
                    // doRound=false debe devolver el producto crudo.
                    const unrounded = order._convert(amount, from, to, false);
                    expect(Math.abs(unrounded - amount * rawRate)).toBeLessThan(1e-9);

                    // Determinismo: mismas entradas, mismo resultado.
                    expect(order._convert(amount, from, to)).toBe(converted);
                }
            }
        }
    });

    test("monto 0/falsy → 0, sin necesidad de tasa configurada", () => {
        const order = makeOrderThis({ config: {} });
        const cur = makeCurrencyWithId(1);
        expect(order._convert(0, cur, cur)).toBe(0);
    });

    test("misma moneda → solo redondea, no requiere moneda foránea configurada", () => {
        const order = makeOrderThis({ config: {} });
        const cur = makeCurrencyWithId(1, 0.01);
        expect(order._convert(1.005, cur, cur)).toBe(cur.round(1.005));
    });

    test("sin tasa disponible → 0, no lanza", () => {
        const order = makeOrderThis({ config: {} });
        const main = makeCurrencyWithId(1);
        const foreign = makeCurrencyWithId(2);
        // foreign_currency_id nunca se configuró: no hay tasa para ninguna
        // dirección.
        expect(() => order._convert(100, main, foreign)).not.toThrow();
        expect(order._convert(100, main, foreign)).toBe(0);
    });

    test("empate exacto redondea HALF-UP (lejos de cero), no HALF-EVEN", () => {
        // 0.125 es representable exactamente en binario y es un empate
        // exacto a 2 decimales (equidistante de 0.12 y 0.13). Mismo caso
        // usado en el lado Python
        // (test_pos_config_convert_precision.py::test_convert_half_up_tie_breaks_away_from_zero)
        // para blindar que cliente y servidor redondean igual.
        const order = makeOrderThis({ config: {} });
        const cur = makeCurrencyWithId(1, 0.01);
        expect(order._convert(0.125, cur, cur)).toBe(0.13);
    });
});

describe("l10n_ve_pos localToForeign/foreignToLocal", () => {
    test("delegan en _convert con las monedas correctas, en ambas direcciones", () => {
        for (const bsPerUsd of BS_PER_USD_RATES) {
            const { order, main, foreign } = makeOrderWithRate(bsPerUsd);
            for (const amount of AMOUNTS) {
                expect(order.localToForeign(amount)).toBe(
                    order._convert(amount, main, foreign)
                );
                expect(order.foreignToLocal(amount)).toBe(
                    order._convert(amount, foreign, main)
                );
            }
        }
    });

    test("ida y vuelta recupera el monto original dentro de un paso de redondeo", () => {
        const { order } = makeOrderWithRate(36.567891234);
        for (const amount of AMOUNTS) {
            const foreignAmount = order.localToForeign(amount);
            const back = order.foreignToLocal(foreignAmount);
            expect(Math.abs(back - amount)).toBeLessThan(0.02);
        }
    });

    test("doRound=false se propaga desde los atajos hasta _convert", () => {
        const { order, main, foreign } = makeOrderWithRate(36.567891234);
        const amount = 33.33;
        expect(order.localToForeign(amount, false)).toBe(
            order._convert(amount, main, foreign, false)
        );
    });
});
