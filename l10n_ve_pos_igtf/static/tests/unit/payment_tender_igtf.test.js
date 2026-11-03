import { describe, expect, test } from "@odoo/hoot";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import "@l10n_ve_pos/overrides/models/payment_model";
import "@l10n_ve_pos_igtf/app/overrides/models/payment_model";

// Tarea 86066: el cobro en una tercera moneda (EUR) de l10n_ve_pos
// (setTenderAmount) parte del restante de la caja ANTES de la línea
// (_getLocalDueBefore). Con IGTF, ese restante es la base de factura pendiente
// más la deuda IGTF, sin el IGTF que la línea generará: el mismo que usa
// set_foreign_amount para la alterna.

const round2 = (amount) => Math.round(amount * 100) / 100;

// `this` hecho a mano sobre el prototipo (con getters): Object.assign no puede
// pisarlos, se definen como propiedades propias.
function makeLine(own) {
    return Object.create(
        PosPayment.prototype,
        Object.fromEntries(
            Object.entries(own).map(([key, value]) => [key, { value, writable: true }])
        )
    );
}

function makeOrder({ toInvoice = true, igtfAmount = 0, base = { sign: 1, remainingBase: 0, unpaidIgtf: 0 }, totalDue = 0 } = {}) {
    return {
        to_invoice: toInvoice,
        igtf_amount: igtfAmount,
        totalDue,
        payment_ids: [],
        _igtfRoundLocal: round2,
        _igtfBaseState: () => base,
    };
}

function makeOtherLine(amount) {
    return { isDone: () => true, is_change: false, getAmount: () => amount };
}

describe("l10n_ve_pos_igtf: restante para la moneda de cobro", () => {
    test("con un método que aplica IGTF, base pendiente más deuda IGTF", () => {
        const order = makeOrder({ base: { sign: 1, remainingBase: 100.004, unpaidIgtf: 3 } });
        const line = makeLine({ pos_order_id: order, payment_method_id: { apply_igtf: true } });
        expect(line._getLocalDueBefore()).toBe(103);
    });

    test("en un reembolso, con el signo del restante", () => {
        const order = makeOrder({ base: { sign: -1, remainingBase: 100, unpaidIgtf: 3 } });
        const line = makeLine({ pos_order_id: order, payment_method_id: { apply_igtf: true } });
        expect(line._getLocalDueBefore()).toBe(-103);
    });

    test("con deuda IGTF acumulada, aunque el método no aplique IGTF", () => {
        const order = makeOrder({
            igtfAmount: 3,
            base: { sign: 1, remainingBase: 50, unpaidIgtf: 3 },
        });
        const line = makeLine({ pos_order_id: order, payment_method_id: { apply_igtf: false } });
        expect(line._getLocalDueBefore()).toBe(53);
    });

    test("sin factura (sin contexto IGTF), el restante de l10n_ve_pos", () => {
        const order = makeOrder({
            toInvoice: false,
            totalDue: 50,
            base: { sign: 1, remainingBase: 999, unpaidIgtf: 9 },
        });
        const line = makeLine({ pos_order_id: order, payment_method_id: { apply_igtf: true } });
        order.payment_ids = [line, makeOtherLine(20)];
        expect(line._getLocalDueBefore()).toBe(30);
    });
});
