import { test, expect, describe } from "@odoo/hoot";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import "@l10n_ve_pos/overrides/models/pos_order_line";

// Ticket 16547: la línea [DISC] del descuento global tiene precio NEGATIVO y
// `_get_raw_foreign_unit_price` devolvía 0 para todo precio <= 0, así que se
// sincronizaba con foreign_price = 0 y la factura quedaba con el alterno sin
// descontar. El precio foráneo debe conservar el signo.
//
// Sin `makeMockEnv`: `setUnitPrice` no necesita el entorno de servicios, y el
// de `pos_order_line_discount.test.js` falla al arrancar en las bases con
// `pos_discount` (RPC a `pos.config` sin definir en el mock).

const DISCOUNT_PRODUCT_ID = 42;

const DECIMAL_PRECISION = [{ name: "Product Price", round: (v) => Math.round(v * 100) / 100 }];

// Base en Bs, alterna en USD a 500: el PdV convierte con el multiplicador 1 / 500.
const order = { localToForeign: (amount) => amount * 0.002 };

function makeDiscountLine(props = {}) {
    const line = Object.create(PosOrderline.prototype);
    const defaults = {
        config: { discount_product_id: { id: DISCOUNT_PRODUCT_ID } },
        product_id: { id: DISCOUNT_PRODUCT_ID },
        order_id: order,
        refunded_orderline_id: false,
        models: { "decimal.precision": DECIMAL_PRECISION },
    };
    for (const [key, value] of Object.entries({ ...defaults, ...props })) {
        Object.defineProperty(line, key, { value, configurable: true, writable: true });
    }
    return line;
}

describe("l10n_ve_pos foreign_price de la línea de descuento (ticket 16547)", () => {
    test("la línea de descuento guarda el precio foráneo negativo", () => {
        const line = makeDiscountLine();
        line.setUnitPrice(-1350);
        expect(line.price_unit).toBe(-1350);
        expect(line.foreign_price).toBe(-2.7);
        expect(line.get_foreign_unit_price()).toBe(-2.7);
    });

    test("monto positivo coaccionado a negativo: el foráneo sigue el signo", () => {
        const line = makeDiscountLine();
        line.setUnitPrice(1800);
        expect(line.price_unit).toBe(-1800);
        expect(line.foreign_price).toBe(-3.6);
    });

    test("sin foreign_price guardado, el unitario foráneo se calcula del precio negativo", () => {
        const line = makeDiscountLine({ price_unit: -1350, foreign_price: 0 });
        expect(line.get_foreign_unit_price()).toBe(-2.7);
    });

    test("precio en cero sigue dando foráneo en cero", () => {
        const line = makeDiscountLine();
        line.setUnitPrice(0);
        expect(line.foreign_price).toBe(0);
    });
});
