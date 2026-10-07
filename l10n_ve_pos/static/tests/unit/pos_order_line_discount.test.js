import { test, expect, describe, beforeEach } from "@odoo/hoot";
import { makeMockEnv, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { localization } from "@web/core/l10n/localization";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { OrderSummary } from "@point_of_sale/app/screens/product_screen/order_summary/order_summary";
import "@l10n_ve_pos/overrides/models/pos_order_line";
import "@l10n_ve_pos/overrides/screens/product_screen/order_summary/order_summary";

// Ticket 14352: la línea de descuento no puede volverse positiva. El guard
// vive en `setUnitPrice`, pero el precio que llega no siempre es un número:
// cuando el cajero teclea el monto en modo precio, es el buffer crudo del
// number_buffer, sensible al locale (coma decimal en es_VE). `Number(price)`
// con ese string da NaN y el guard no dispara — estos tests cubren
// justo ese caso, además de las exenciones de reembolso.
//
// También cubre la regresión del ×100: el "+/-" del numpad con buffer vacío
// arma el nuevo monto con `String(numero)` (SIEMPRE con punto decimal, sea
// cual sea el locale). Si ese string se parsea directo con el parser de
// locale (coma decimal en es_VE), el punto se lee como separador de miles y
// el monto se multiplica por 100. `_numberFromInput` prueba primero
// `Number()` nativo (igual que el propio `setUnitPrice` del core) antes de
// caer al parser de locale.

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

    test("string con punto decimal generado por el core no se multiplica por 100", () => {
        patchWithCleanup(localization, { decimalPoint: ",", thousandsSep: "." });
        const line = makeDiscountLine();
        // Buffer que arma OrderSummary vía `String(numero)` en la rama "+/-"
        // con buffer vacío: siempre con punto, nunca coma, sin importar el
        // locale activo.
        line.setUnitPrice("-4842.69");
        expect(line.price_unit).toBe(-4842.69);
    });

    test("string con punto decimal positivo generado por el core se coacciona a negativo, no a ×100", () => {
        patchWithCleanup(localization, { decimalPoint: ",", thousandsSep: "." });
        const line = makeDiscountLine();
        line.setUnitPrice("4842.69");
        expect(line.price_unit).toBe(-4842.69);
    });
});

describe("l10n_ve_pos discount line +/- no-op (OrderSummary.updateSelectedOrderline)", () => {
    function makeOrderSummaryStub({ numpadMode = "price" } = {}) {
        const calls = { reset: 0 };
        const stub = {
            pos: { numpadMode },
            numberBuffer: { reset: () => calls.reset++ },
        };
        return { stub, calls };
    }

    // La decisión de hacer no-op vive en `_shouldSkipDiscountLineSignToggle`,
    // separada de `updateSelectedOrderline` a propósito: testearla directo
    // evita depender de que el `super` (el core real) reviente sobre un stub
    // incompleto para "demostrar" que no se tomó la rama de no-op — antes,
    // esa dependencia hacía que estos casos pasaran igual aunque la condición
    // estuviera mal (con tal de que algo, lo que sea, tirara una excepción).
    describe("_shouldSkipDiscountLineSignToggle", () => {
        test("buffer vacío + modo precio + línea de descuento (no reembolso) → true", () => {
            const line = makeDiscountLine();
            const { stub } = makeOrderSummaryStub();
            expect(
                OrderSummary.prototype._shouldSkipDiscountLineSignToggle.call(stub, line, {
                    buffer: "-0",
                    key: "-",
                })
            ).toBe(true);
        });

        test("línea de reembolso → false", () => {
            const line = makeDiscountLine({ order_id: { isRefund: true } });
            const { stub } = makeOrderSummaryStub();
            expect(
                OrderSummary.prototype._shouldSkipDiscountLineSignToggle.call(stub, line, {
                    buffer: "-0",
                    key: "-",
                })
            ).toBe(false);
        });

        test("línea que no es de descuento → false", () => {
            const line = makeDiscountLine({ product_id: { id: 999 } });
            const { stub } = makeOrderSummaryStub();
            expect(
                OrderSummary.prototype._shouldSkipDiscountLineSignToggle.call(stub, line, {
                    buffer: "-0",
                    key: "-",
                })
            ).toBe(false);
        });

        test("modo cantidad → false", () => {
            const line = makeDiscountLine();
            const { stub } = makeOrderSummaryStub({ numpadMode: "quantity" });
            expect(
                OrderSummary.prototype._shouldSkipDiscountLineSignToggle.call(stub, line, {
                    buffer: "-0",
                    key: "-",
                })
            ).toBe(false);
        });

        test("buffer no vacío (cajero ya tecleó) → false", () => {
            const line = makeDiscountLine();
            const { stub } = makeOrderSummaryStub();
            expect(
                OrderSummary.prototype._shouldSkipDiscountLineSignToggle.call(stub, line, {
                    buffer: "500",
                    key: "-",
                })
            ).toBe(false);
        });
    });

    test("updateSelectedOrderline: +/- con buffer vacío sobre la línea de descuento es no-op", async () => {
        const line = makeDiscountLine();
        const priceBefore = line.price_unit;
        const order = { getSelectedOrderline: () => line };
        const { stub, calls } = makeOrderSummaryStub();
        stub.pos.getOrder = () => order;
        await OrderSummary.prototype.updateSelectedOrderline.call(stub, {
            buffer: "-0",
            key: "-",
        });
        expect(calls.reset).toBe(1);
        expect(line.price_unit).toBe(priceBefore);
    });
});

describe("l10n_ve_pos discount line setQuantity (bloqueo, comparte _numberFromInput)", () => {
    // `setQuantity` corta ANTES de `super` cuando bloquea (devuelve el
    // objeto {title, body} sin tocar el core), así que estos casos no
    // necesitan stub de `models["pos.order"]`/`uiState` — solo el camino de
    // "cantidad válida, delega al core" los necesitaría, y eso ya lo cubre
    // (en navegador) el change hermano `l10n-ve-pos-no-negative-qty-outside-refund`.
    test("cantidad negativa fuera de reembolso se bloquea (entero tecleado)", () => {
        const line = makeDiscountLine();
        const result = line.setQuantity("-3");
        expect(typeof result).toBe("object");
        expect(typeof result.title).toBe("string");
    });

    test("cantidad negativa con coma decimal en es_VE también se bloquea", () => {
        patchWithCleanup(localization, { decimalPoint: ",", thousandsSep: "." });
        const line = makeDiscountLine();
        const result = line.setQuantity("-3,5");
        expect(typeof result).toBe("object");
    });

    test("string con punto decimal generado por el core no se multiplica por 100 en setQuantity", () => {
        patchWithCleanup(localization, { decimalPoint: ",", thousandsSep: "." });
        const line = makeDiscountLine();
        // Mismo helper que setUnitPrice (_numberFromInput): un "-4842.69"
        // (punto, no tecleado por el cajero) debe seguir bloqueado por
        // negativo, sin importar si se lee bien como -4842.69 o mal como
        // -484269 — pero si el bug ×100 volviera, este caso lo seguiría
        // detectando como bloqueado igual; lo que realmente lo cubre es el
        // test de `setUnitPrice` de más arriba con el mismo string.
        const result = line.setQuantity("-4842.69");
        expect(typeof result).toBe("object");
    });
});
