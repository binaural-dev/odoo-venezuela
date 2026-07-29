import { test, expect, describe } from "@odoo/hoot";
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import "@l10n_ve_pos/overrides/screens/payment_status/payment_status";
import { makeCurrency, makeOrderStub } from "./utils";

// _clampToZeroForeign: nunca mostrar restante/cambio foráneo negativo, y
// tratar residuos por debajo del rounding como cero (isPositive).

function clamp(value, order) {
    return PaymentScreenStatus.prototype._clampToZeroForeign.call(
        { props: { order } },
        value
    );
}

describe("l10n_ve_pos _clampToZeroForeign", () => {
    test("positivos pasan, negativos se muestran como cero", () => {
        const order = makeOrderStub({ fc: makeCurrency(0.01) });
        expect(clamp(5.25, order)).toBe(5.25);
        expect(clamp(-3, order)).toBe(0);
        expect(clamp(0, order)).toBe(0);
    });

    test("residuo sub-rounding cuenta como cero en ambos signos", () => {
        const order = makeOrderStub({ fc: makeCurrency(0.01) });
        expect(clamp(-0.004, order)).toBe(0);
        // Antes Math.max(0, 0.004) dejaba pasar el ruido positivo.
        expect(clamp(0.004, order)).toBe(0);
    });

    test("sin moneda resuelta: respaldo con ternario simple", () => {
        expect(clamp(5.25, {})).toBe(5.25);
        expect(clamp(-3, {})).toBe(0);
        expect(clamp(0.004, {})).toBe(0.004);
        expect(clamp(5.25, undefined)).toBe(5.25);
    });
});
