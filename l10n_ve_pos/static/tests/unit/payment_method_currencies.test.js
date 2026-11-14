import { test, expect, describe } from "@odoo/hoot";
import { PosPaymentMethod } from "@point_of_sale/app/models/pos_payment_method";
import "@l10n_ve_pos/overrides/models/pos_payment_method";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import "@l10n_ve_pos/overrides/screens/payment_screen/payment_screen";

// El core pone la moneda de la caja de primera en `availableCurrencies`, aunque
// el método no la acepte. En 19 Zelle no tenía opción en bolívares: un método
// cuyo `currency_ids` no incluye la moneda de la caja no la ofrece.

const VEF = { id: 2, name: "VEF" };
const USD = { id: 1, name: "USD" };
const EUR = { id: 3, name: "EUR" };

function availableCurrencies({ type = "bank", currency_ids }) {
    const method = {
        type,
        currency_ids,
        config: { currency_id: VEF },
    };
    return Object.getOwnPropertyDescriptor(
        PosPaymentMethod.prototype,
        "availableCurrencies"
    ).get.call(method);
}

describe("l10n_ve_pos PosPaymentMethod.availableCurrencies", () => {
    test("Zelle (solo dólares) no ofrece la moneda de la caja", () => {
        expect(availableCurrencies({ currency_ids: [USD] })).toEqual([USD]);
    });

    test("el efectivo con bolívares, dólares y euros conserva las tres", () => {
        expect(availableCurrencies({ type: "cash", currency_ids: [VEF, USD, EUR] })).toEqual([
            VEF,
            USD,
            EUR,
        ]);
    });

    test("la moneda de la caja va primero aunque se haya cargado después", () => {
        expect(availableCurrencies({ type: "cash", currency_ids: [USD, VEF, EUR] })).toEqual([
            VEF,
            USD,
            EUR,
        ]);
    });

    test("sin monedas el método ofrece la de la caja, como el core", () => {
        expect(availableCurrencies({ currency_ids: [] })).toEqual([VEF]);
    });

    test("un método que no es de banco ni efectivo ofrece la de la caja", () => {
        expect(availableCurrencies({ type: "pay_later", currency_ids: [USD] })).toEqual([VEF]);
    });
});

describe("l10n_ve_pos PaymentScreen.addNewPaymentLine con un solo botón", () => {
    function makeScreen() {
        const added = [];
        const screen = {
            dialog: { add: () => {} },
            paymentLines: [{}],
            numberBuffer: { set: () => {} },
            pos: { config: { currency_id: VEF }, formatCurrency: () => "" },
            currentOrder: {
                remainingDue: 0,
                addPaymentline: (method, args) => {
                    added.push(args);
                    return { status: true, data: { amount: 0, isForeignPayment: false } };
                },
            },
            isRefundOrder: false,
        };
        return { screen, added };
    }

    function click(screen, method, args) {
        return PaymentScreen.prototype.addNewPaymentLine.call(screen, method, args);
    }

    const zelle = {
        availableCurrencies: [USD],
        getPaymentInterfaceStates: () => ({ status: true, message: "" }),
        useBankQrCode: false,
    };

    test("Zelle sin botones de moneda cobra en dólares", async () => {
        const { screen, added } = makeScreen();
        await click(screen, zelle);
        expect(added[0].currency).toBe(USD);
    });

    test("un método que acepta la moneda de la caja no cambia sus argumentos", async () => {
        const { screen, added } = makeScreen();
        await click(screen, { ...zelle, availableCurrencies: [VEF] });
        expect(added[0].currency).toBe(undefined);
    });

    test("la moneda de un botón se respeta", async () => {
        const { screen, added } = makeScreen();
        await click(screen, { ...zelle, availableCurrencies: [VEF, USD] }, { currency: USD });
        expect(added[0].currency).toBe(USD);
    });
});
