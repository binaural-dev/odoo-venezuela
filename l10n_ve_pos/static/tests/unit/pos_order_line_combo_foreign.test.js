import { test, expect, describe } from "@odoo/hoot";
import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import "@l10n_ve_pos/overrides/models/pos_order_line";

// Ticket 15725: en la línea padre de un combo el monto foráneo salía en 0. El
// padre no tiene precio propio (el core reparte el precio del combo entre las
// hijas y su displayPrice es la suma de ellas), así que el monto foráneo que se
// muestra tiene que ser la suma de los de las hijas, con o sin impuestos según
// iface_tax_included. Tasa en vivo 0,025 $/Bs; la venta original del reembolso
// se hizo a 0,02 $/Bs.

const round2 = (amount) => Math.round(amount * 100) / 100;

function makeOrder() {
    return {
        localToForeign: (amount) => round2(amount * 0.025),
        localToForeignAtRate: (amount, rate) => round2(amount * rate),
        roundForeignMoney: round2,
        _isFrozenRateOrder: () => false,
    };
}

function makeLine(props = {}) {
    const line = Object.create(PosOrderline.prototype);
    const values = { combo_line_ids: [], refunded_orderline_id: null, ...props };
    for (const [key, value] of Object.entries(values)) {
        Object.defineProperty(line, key, { value, configurable: true, writable: true });
    }
    return line;
}

function makeCombo({ taxIncluded, refundedRate = null }) {
    const order = makeOrder();
    const config = { iface_tax_included: taxIncluded ? "total" : "subtotal" };
    const refunded = refundedRate && {
        order_id: { foreign_currency_rate: refundedRate },
    };
    // Hijas: 464 Bs (400 + IVA 16 %) y 216 Bs (200 + IVA 8 %).
    const children = [
        makeLine({ order_id: order, config, priceIncl: 464, priceExcl: 400, refunded_orderline_id: refunded }),
        makeLine({ order_id: order, config, priceIncl: 216, priceExcl: 200, refunded_orderline_id: refunded }),
    ];
    const parent = makeLine({
        order_id: order,
        config,
        priceIncl: 0,
        priceExcl: 0,
        combo_line_ids: children,
        refunded_orderline_id: refunded,
    });
    return { parent, children };
}

describe("l10n_ve_pos monto foráneo de los combos (ticket 15725)", () => {
    test("impuestos incluidos: el padre muestra la suma con impuestos de sus hijas", () => {
        const { parent } = makeCombo({ taxIncluded: true });
        // Antes: get_foreign_price_with_tax() del padre = 0.
        expect(parent.get_foreign_price_with_tax()).toBe(0);
        // 464 × 0,025 + 216 × 0,025 = 11,60 + 5,40
        expect(parent.get_foreign_display_price()).toBe(17);
    });

    test("impuestos excluidos: el padre muestra la suma sin impuestos de sus hijas", () => {
        const { parent } = makeCombo({ taxIncluded: false });
        // 400 × 0,025 + 200 × 0,025 = 10 + 5
        expect(parent.get_foreign_display_price()).toBe(15);
    });

    test("línea normal: muestra su propio monto, como antes", () => {
        const { children } = makeCombo({ taxIncluded: true });
        expect(children[0].get_foreign_display_price()).toBe(11.6);
        const { children: excluded } = makeCombo({ taxIncluded: false });
        expect(excluded[0].get_foreign_display_price()).toBe(10);
    });

    test("reembolso: las hijas se convierten a la tasa de la venta original", () => {
        const { parent } = makeCombo({ taxIncluded: true, refundedRate: 0.02 });
        // 464 × 0,02 + 216 × 0,02 = 9,28 + 4,32 (a la tasa de hoy serían 17)
        expect(parent.get_foreign_display_price()).toBe(13.6);
    });
});
