import { test, expect, describe } from "@odoo/hoot";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import "@l10n_ve_pos/overrides/screens/payment_screen/payment_screen";
import { makeCurrency } from "./utils";

// updateSelectedPaymentline (rama foránea): validación de monto máximo en
// métodos no-efectivo, en magnitudes y con precisión de la moneda local.

function makeScreenStub({ due, lineAmount = 0, cash = false }) {
    const calls = { setAmount: [], bufferSet: [], foreign: [], maxErr: 0 };
    const stub = {
        paymentLines: [{ paid: false }],
        selectedPaymentLine: {
            payment_method_id: { is_foreign_currency: true },
            amount: lineAmount,
            uuid: "uuid-test",
            setAmount: (v) => calls.setAmount.push(v),
            set_foreign_amount: (v) => calls.foreign.push(v),
            getPaymentStatus: () => "pending",
        },
        payment_methods_from_config: [{ type: cash ? "cash" : "bank" }],
        currentOrder: { remainingDue: due },
        pos: { currency: makeCurrency(0.01) },
        numberBuffer: { get: () => "", getFloat: () => 0, set: (v) => calls.bufferSet.push(v) },
        showMaxValueError: () => calls.maxErr++,
    };
    return { stub, calls };
}

function update(stub, amount) {
    PaymentScreen.prototype.updateSelectedPaymentline.call(stub, amount);
}

describe("l10n_ve_pos updateSelectedPaymentline (foránea)", () => {
    test("monto que excede lo adeudado se recorta al máximo", () => {
        const { stub, calls } = makeScreenStub({ due: 100 });
        update(stub, 150);
        expect(calls.maxErr).toBe(1);
        expect(calls.setAmount).toEqual([0]);
        expect(calls.bufferSet).toEqual(["100"]);
        expect(calls.foreign).toEqual([100]);
    });

    test("monto dentro del límite pasa directo", () => {
        const { stub, calls } = makeScreenStub({ due: 100 });
        update(stub, 80);
        expect(calls.maxErr).toBe(0);
        expect(calls.foreign).toEqual([80]);
    });

    test("exceso sub-rounding no dispara el error (comp con precisión)", () => {
        const { stub, calls } = makeScreenStub({ due: 100 });
        update(stub, 100.004);
        expect(calls.maxErr).toBe(0);
        expect(calls.foreign).toEqual([100.004]);
    });

    test("reembolso: la magnitud manda y el máximo es |deuda|", () => {
        const { stub, calls } = makeScreenStub({ due: -100 });
        update(stub, -150);
        expect(calls.maxErr).toBe(1);
        expect(calls.bufferSet).toEqual(["100"]);
        expect(calls.foreign).toEqual([100]);
    });

    test("con método efectivo disponible no se limita", () => {
        const { stub, calls } = makeScreenStub({ due: 100, cash: true });
        update(stub, 150);
        expect(calls.maxErr).toBe(0);
        expect(calls.foreign).toEqual([150]);
    });

    test("la línea previa cuenta para el límite", () => {
        const { stub, calls } = makeScreenStub({ due: 40, lineAmount: 60 });
        update(stub, 90);
        expect(calls.maxErr).toBe(0);
        expect(calls.foreign).toEqual([90]);
    });
});
