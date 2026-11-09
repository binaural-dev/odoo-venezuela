import { test, expect, describe } from "@odoo/hoot";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import "@l10n_ve_pos/overrides/models/pos_order";

// Tasa de los pagos al sincronizar la orden (tarea 83148, H7).
//
// El core serializa los pagos anidados en la orden con `deepSerialization`
// (campos crudos), sin pasar por `PosPayment.serializeForORM`, así que la tasa
// del pago llegaba en 0. `PosOrder.serializeForORM` la pone en cada comando de
// `payment_ids`, emparejando por uuid, como hace l10n_ve_pos_igtf con sus
// campos. La tasa es la efectiva de la orden (`get_effective_foreign_multiplier`),
// la misma con la que el PdV calcula el `foreign_amount` de cada línea.
//
// Mismo patrón que pos_order_conversion.test.js: prototipo REAL de PosOrder y
// defineProperty, porque el prototipo tiene getters sin setter.
function makeOrderThis(props = {}) {
    const order = Object.create(PosOrder.prototype);
    for (const [key, value] of Object.entries(props)) {
        Object.defineProperty(order, key, { value, configurable: true, writable: true });
    }
    return order;
}

// Comandos de `payment_ids` como los arma deepSerialization: alta [0, 0, vals],
// modificación [1, id, vals] y baja [2, id] (sin vals).
function makePaymentCommands() {
    return [
        [0, 0, { uuid: "pago-nuevo", amount: 9318.74, foreign_amount: 11.6, foreign_rate: 0 }],
        [1, 7, { uuid: "pago-sincronizado", amount: 500, foreign_amount: 0.62, foreign_rate: 0 }],
        [2, 9],
    ];
}

describe("l10n_ve_pos tasa de los pagos al sincronizar", () => {
    test("cada pago de la orden lleva la tasa efectiva", () => {
        const multiplier = 1 / 803.34;
        const order = makeOrderThis({
            payment_ids: [{ uuid: "pago-nuevo" }, { uuid: "pago-sincronizado" }],
            get_effective_foreign_multiplier: () => multiplier,
        });
        const data = { payment_ids: makePaymentCommands() };

        order._setPaymentForeignRates(data);

        expect(data.payment_ids[0][2].foreign_rate).toBe(multiplier);
        expect(data.payment_ids[1][2].foreign_rate).toBe(multiplier);
        // La baja no lleva valores: se deja tal cual.
        expect(data.payment_ids[2]).toEqual([2, 9]);
    });

    test("un comando que no es de un pago de la orden no se toca", () => {
        const order = makeOrderThis({
            payment_ids: [{ uuid: "pago-nuevo" }],
            get_effective_foreign_multiplier: () => 1 / 803.34,
        });
        const data = { payment_ids: makePaymentCommands() };

        order._setPaymentForeignRates(data);

        expect(data.payment_ids[1][2].foreign_rate).toBe(0);
    });

    test("un reembolso lleva la tasa de la venta original", () => {
        // Tasa exacta del pago foráneo original (prefetch de
        // get_refund_foreign_rate): 795 Bs por $, no la de hoy.
        const order = makeOrderThis({
            payment_ids: [{ uuid: "pago-nuevo" }],
            refund_foreign_rate: 795,
        });
        const data = { payment_ids: [[0, 0, { uuid: "pago-nuevo", amount: -9222.6, foreign_rate: 0 }]] };

        order._setPaymentForeignRates(data);

        expect(data.payment_ids[0][2].foreign_rate).toBe(1 / 795);
    });

    test("serializeForORM de la orden pone la tasa en sus pagos", () => {
        // Pasa por el serializeForORM real (el de l10n_ve_pos y los del core):
        // el modelo devuelve lo que daría deepSerialization, sin tasa.
        const multiplier = 1 / 803.34;
        const serialized = { payment_ids: makePaymentCommands() };
        const order = makeOrderThis({
            model: { serializeForORM: () => serialized },
            payment_ids: [{ uuid: "pago-nuevo" }, { uuid: "pago-sincronizado" }],
            get_paymentlines: () => [],
            get_foreign_total_with_tax: () => 11.6,
            init_conversion_rate: multiplier,
            get_effective_foreign_multiplier: () => multiplier,
        });

        const data = order.serializeForORM();

        expect(data.payment_ids[0][2].foreign_rate).toBe(multiplier);
        expect(data.payment_ids[1][2].foreign_rate).toBe(multiplier);
    });

    test("sin pagos no falla", () => {
        const order = makeOrderThis({
            payment_ids: [],
            get_effective_foreign_multiplier: () => 1 / 803.34,
        });
        const data = {};

        order._setPaymentForeignRates(data);

        expect(data).toEqual({});
    });
});
