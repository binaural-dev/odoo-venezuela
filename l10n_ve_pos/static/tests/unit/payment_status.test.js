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

function amountText(order) {
    const { get } = Object.getOwnPropertyDescriptor(PaymentScreenStatus.prototype, "amountText");
    const pos = { formatCurrency: (amount, currencyId) => `${currencyId}:${amount}` };
    return get.call({ props: { order }, pos });
}

describe("l10n_ve_pos amountText", () => {
    const register = { id: 2 };
    const firstPaymentCurrency = { id: 1 };

    test("remaining amount in the register currency with a first payment in foreign currency", () => {
        const order = {
            currency: register,
            orderCurrency: firstPaymentCurrency,
            hasRemainingDue: true,
            remainingDue: 3249.56,
            change: 0,
        };
        expect(amountText(order)).toBe("2:3249.56");
    });

    test("change in the register currency once nothing remains", () => {
        const order = {
            currency: register,
            orderCurrency: firstPaymentCurrency,
            hasRemainingDue: false,
            remainingDue: -14257.34,
            change: 14257.34,
        };
        expect(amountText(order)).toBe("2:14257.34");
    });
});
