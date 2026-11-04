import { test, expect, describe } from "@odoo/hoot";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import "@l10n_ve_pos/overrides/models/pos_order";
import { makeCurrency } from "./utils";

// Signo del total foráneo de un reembolso (tarea 83148, H1).
//
// En Odoo 19 el core da el priceIncl de cada línea multiplicado por
// order.orderSign (-1 en un reembolso): una magnitud POSITIVA para mostrar,
// mientras totalDue sigue NEGATIVO. Sumar esas magnitudes daba un total
// foráneo positivo, y con él una tasa negativa (total foráneo / totalDue) que
// invertía el signo de foreign_amount en los pagos del reembolso.
//
// Mismo patrón que pos_order_conversion.test.js: prototipo REAL de PosOrder y
// defineProperty, porque el prototipo tiene getters sin setter (orderSign,
// config).
function makeOrderThis(props = {}) {
    const order = Object.create(PosOrder.prototype);
    for (const [key, value] of Object.entries(props)) {
        Object.defineProperty(order, key, { value, configurable: true, writable: true });
    }
    return order;
}

// Línea como la deja el core: importes ya multiplicados por orderSign.
function makeLine({ withTax, withoutTax, refunded = true }) {
    return {
        refunded_orderline_id: refunded ? { id: 1 } : false,
        get_foreign_price_with_tax: () => withTax,
        get_foreign_price_without_tax: () => withoutTax,
        get_foreign_total_tax: () => withTax - withoutTax,
    };
}

// Reembolso de 1 × "Producto IVA16 10 USD" de la prueba e2e: −9.318,74 Bs a
// la tasa original, que son 11,60 $ (10,00 $ de base + 1,60 $ de IVA).
function makeRefund(lines = [makeLine({ withTax: 11.6, withoutTax: 10 })], totalDue = -9318.74) {
    return makeOrderThis({
        lines,
        totalDue,
        orderSign: -1,
        refund_foreign_rate: 0,
        currency: makeCurrency(0.01),
        config: { foreign_currency_id: makeCurrency(0.01) },
    });
}

describe("l10n_ve_pos signo del total foráneo de un reembolso", () => {
    test("los totales foráneos llevan el signo del total local", () => {
        const order = makeRefund();
        expect(order.get_foreign_total_with_tax()).toBe(-11.6);
        expect(order.get_foreign_total_without_tax()).toBe(-10);
        expect(order.get_foreign_total_tax()).toBe(-1.6);
    });

    test("el restante local se convierte con su signo", () => {
        const order = makeRefund();
        expect(order._convertOrderAmount(-9318.74)).toBe(-11.6);
        expect(order._convertForeignOrderAmount(-11.6)).toBe(-9318.74);
    });

    test("la tasa estampada en el pago sale positiva sin quitarle el signo", () => {
        const order = makeRefund();
        expect(order.get_effective_foreign_multiplier()).toBe(11.6 / 9318.74);
    });

    test("orden mixta (reembolso más venta) conserva el neto con signo", () => {
        // Con orderSign -1 el core invierte también la línea de venta: 5 $
        // vendidos llegan como -5. El neto real es -11,60 + 5 = -6,60 $.
        const order = makeRefund(
            [
                makeLine({ withTax: 11.6, withoutTax: 10 }),
                makeLine({ withTax: -5, withoutTax: -5, refunded: false }),
            ],
            -5302.04
        );
        expect(order.get_foreign_total_with_tax()).toBe(-6.6);
    });

    test("cambio con signos netos opuestos no estampa una tasa negativa", () => {
        // Reembolso de 10 $ a 36,5 (-365 Bs) más venta de 9,5 $ a 40
        // (+380 Bs): local +15 Bs, foráneo -0,5 $. Cae a la tasa viva.
        const order = makeRefund(
            [
                makeLine({ withTax: 10, withoutTax: 10 }),
                makeLine({ withTax: -9.5, withoutTax: -9.5, refunded: false }),
            ],
            15
        );
        Object.defineProperty(order, "get_foreign_multiplier", { value: () => 1 / 40 });
        expect(order.get_foreign_total_with_tax()).toBe(-0.5);
        expect(order.get_effective_foreign_multiplier()).toBe(1 / 40);
    });
});
