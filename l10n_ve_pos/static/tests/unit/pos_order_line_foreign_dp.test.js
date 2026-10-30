import { test, expect, describe } from "@odoo/hoot";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import "@l10n_ve_pos/overrides/models/pos_order_line";

// Ticket #15106: el precio unitario foráneo (foreign_price) debe redondearse a la
// precisión decimal de catálogo "Foreign Product Price" (p. ej. 6), NO a los 2
// decimales de la moneda. En Odoo 19 esa dp llega en
// `this.pos.models["decimal.precision"]`; el `this.pos.dp[...]` de Odoo 17 no
// existe y hacía caer SIEMPRE al fallback de 2 dp — con lo que la suma de las
// líneas (foreign_price * cantidad) se desviaba del total que el PdV cobró.

function makeLineThis(props = {}) {
    const line = Object.create(PosOrderline.prototype);
    for (const [key, value] of Object.entries(props)) {
        Object.defineProperty(line, key, { value, configurable: true, writable: true });
    }
    return line;
}

function makeModels(foreignProductPriceDp) {
    const records = [];
    if (foreignProductPriceDp !== undefined) {
        records.push({ name: "Foreign Product Price", digits: foreignProductPriceDp });
    }
    // Array nativo → tiene .find(), igual que el recordset del cliente O19.
    return { "decimal.precision": records };
}

describe("l10n_ve_pos _foreignUnitPriceDp (ticket #15106)", () => {
    test("usa la dp 'Foreign Product Price' de models['decimal.precision'] (Odoo 19)", () => {
        const line = makeLineThis({
            models: makeModels(6),
            get_foreign_currency: () => ({ decimal_places: 2 }),
        });
        // Si leyera el inexistente this.pos.dp caería al fallback 2; debe dar 6.
        expect(line._foreignUnitPriceDp()).toBe(6);
    });

    test("sin la dp cargada, cae a los decimales de la moneda foránea", () => {
        const line = makeLineThis({
            models: makeModels(undefined),
            get_foreign_currency: () => ({ decimal_places: 2 }),
        });
        expect(line._foreignUnitPriceDp()).toBe(2);
    });

    test("get_foreign_unit_price conserva la precisión del catálogo (no la trunca a 2)", () => {
        const line = makeLineThis({
            models: makeModels(6),
            get_foreign_currency: () => ({ decimal_places: 2 }),
            foreign_price: 11.246133,
        });
        // Con la dp de catálogo (6) el precio unitario foráneo NO se trunca a 11.25.
        expect(line.get_foreign_unit_price()).toBe(11.246133);
    });
});
