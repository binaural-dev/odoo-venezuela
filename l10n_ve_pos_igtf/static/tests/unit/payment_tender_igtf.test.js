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

// set_foreign_amount usa la misma condición (hasIgtfContext) que
// _getLocalDueBefore: si lo tecleado en la alterna cubre el restante con IGTF,
// el monto local es ese restante exacto más el excedente convertido.
describe("l10n_ve_pos_igtf: set_foreign_amount en contexto IGTF", () => {
    const BS_PER_USD = 36.5;

    function makeForeignLine() {
        const order = makeOrder({ base: { sign: 1, remainingBase: 100, unpaidIgtf: 3 } });
        Object.assign(order, {
            localToForeign: (amount) => round2(amount / BS_PER_USD),
            foreignToLocal: (amount) => round2(amount * BS_PER_USD),
            roundForeignMoney: round2,
        });
        return makeLine({
            pos_order_id: order,
            payment_method_id: { apply_igtf: true },
            amount: 0,
            foreign_amount: 0,
        });
    }

    test("lo tecleado cubre el restante: el local exacto", () => {
        const line = makeForeignLine();
        // 103 Bs = 2,82 $.
        line.set_foreign_amount(2.82);
        expect(line.amount).toBe(103);
        expect(line.foreign_amount).toBe(2.82);
    });

    test("pagado de más: el restante más el excedente convertido", () => {
        const line = makeForeignLine();
        line.set_foreign_amount(3);
        // 0,18 $ de excedente = 6,57 Bs.
        expect(line.amount).toBe(109.57);
        expect(line.foreign_amount).toBe(3);
    });
});
