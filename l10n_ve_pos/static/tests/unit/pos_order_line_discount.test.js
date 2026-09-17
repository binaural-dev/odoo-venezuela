import { test, expect, describe, beforeEach } from "@odoo/hoot";
import { makeMockEnv, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { localization } from "@web/core/l10n/localization";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import "@l10n_ve_pos/overrides/models/pos_order_line";

// Ticket 14352: la línea de descuento no puede volverse positiva. El guard
// vive en `setUnitPrice`, pero el precio que llega no siempre es un número:
// cuando el cajero teclea el monto en modo precio, es el buffer crudo del
// number_buffer, sensible al locale (coma decimal en es_VE). `Number(price)`
// con ese string da NaN y el guard no dispara — estos tests cubren
// justo ese caso, además de las exenciones de reembolso.

beforeEach(makeMockEnv);

const DISCOUNT_PRODUCT_ID = 42;

const DECIMAL_PRECISION = [{ name: "Product Price", round: (v) => Math.round(v * 100) / 100 }];

function makeDiscountLine(props = {}) {
    const line = Object.create(PosOrderline.prototype);
    const defaults = {
        config: { discount_product_id: { id: DISCOUNT_PRODUCT_ID } },
        product_id: { id: DISCOUNT_PRODUCT_ID },
        order_id: {},
        refunded_orderline_id: false,
        models: { "decimal.precision": DECIMAL_PRECISION },
    };
    for (const [key, value] of Object.entries({ ...defaults, ...props })) {
        Object.defineProperty(line, key, { value, configurable: true, writable: true });
    }
    return line;
}

describe("l10n_ve_pos discount line setUnitPrice", () => {
    test("monto entero tecleado ('500') queda negativo", () => {
        const line = makeDiscountLine();
        line.setUnitPrice("500");
        expect(line.price_unit).toBe(-500);
    });

    test("monto con coma decimal en es_VE ('500,50') queda negativo, no positivo", () => {
        patchWithCleanup(localization, { decimalPoint: ",", thousandsSep: "." });
        const line = makeDiscountLine();
        line.setUnitPrice("500,50");
        expect(line.price_unit).toBe(-500.5);
    });

    test("+/- ya parseado a número sigue quedando negativo", () => {
        const line = makeDiscountLine();
        // Camino del numpad cuando el buffer trae "-0": SWITCHSIGN arma un
        // número (no un string) antes de llegar a setUnitPrice.
        line.setUnitPrice(500);
        expect(line.price_unit).toBe(-500);
    });

    test("orden marcada como reembolso (order_id.isRefund) no se coacciona", () => {
        const line = makeDiscountLine({ order_id: { isRefund: true } });
        line.setUnitPrice(500);
        expect(line.price_unit).toBe(500);
    });

    test("preset de devolución (order_id.preset_id.is_return) no se coacciona", () => {
        const line = makeDiscountLine({ order_id: { preset_id: { is_return: true } } });
        line.setUnitPrice(500);
        expect(line.price_unit).toBe(500);
    });

    test("línea que no es de descuento no se ve afectada", () => {
        const line = makeDiscountLine({ product_id: { id: 999 } });
        line.setUnitPrice(500);
        expect(line.price_unit).toBe(500);
    });
});
