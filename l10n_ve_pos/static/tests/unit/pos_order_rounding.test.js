import { test, expect, describe } from "@odoo/hoot";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import "@l10n_ve_pos/overrides/models/pos_order";
import { makeCurrency } from "./utils";

// _roundWithCurrency: vía principal currency.round(); fallback roundDecimals
// con decimal_places cuando el registro no tiene round().

// Object.create(PosOrder.prototype): _roundWithCurrency usa otros métodos
// del prototipo (_resolveCurrencyRecord), así que el stub debe heredarlos.
// defineProperty y no Object.assign: el prototipo tiene getters sin setter
// (config, models) y la asignación directa lanzaría en modo estricto.
function makeOrderThis(props = {}) {
    const order = Object.create(PosOrder.prototype);
    for (const [key, value] of Object.entries(props)) {
        Object.defineProperty(order, key, { value, configurable: true, writable: true });
    }
    return order;
}

function roundWith(currency, amount, props = {}) {
    return makeOrderThis(props)._roundWithCurrency(currency, amount);
}

describe("l10n_ve_pos _roundWithCurrency", () => {
    test("delega en currency.round() cuando existe", () => {
        expect(roundWith(makeCurrency(0.01), 1.005)).toBe(1.01);
        expect(roundWith(makeCurrency(0.01), -1.005)).toBe(-1.01);
    });

    test("fallback con decimal_places usa roundDecimals (half-up con épsilon)", () => {
        const bare = { decimal_places: 2 };
        // El viejo Math.round(1.005 * 100) / 100 daba 1.00 por flotante.
        expect(roundWith(bare, 1.005)).toBe(1.01);
        expect(roundWith(bare, 2.675)).toBe(2.68);
        expect(roundWith(bare, -1.005)).toBe(-1.01);
    });

    test("fallback sin decimal_places usa 2 decimales", () => {
        expect(roundWith({}, 1.2345)).toBe(1.23);
        expect(roundWith({}, 1.2351)).toBe(1.24);
    });

    test("id pelado se resuelve contra models['res.currency']", () => {
        const fc = makeCurrency(0.01);
        const props = { models: { "res.currency": { get: (id) => (id === 5 ? fc : null) } } };
        expect(roundWith(5, 1.005, props)).toBe(1.01);
    });

    test("roundForeignMoney usa la moneda foránea de la config", () => {
        const order = makeOrderThis({ config: { foreign_currency_id: makeCurrency(0.01) } });
        expect(order.roundForeignMoney(99.256438)).toBe(99.26);
    });
});
