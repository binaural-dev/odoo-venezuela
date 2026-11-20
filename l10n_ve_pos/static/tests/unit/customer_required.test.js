import { describe, expect, test } from "@odoo/hoot";
import { PosOrder } from "@point_of_sale/app/models/pos_order";
import "@l10n_ve_pos/overrides/models/pos_order";

// "Identificar cliente" (split_transactions): Odoo 20 solo pide cliente para el
// método de cuenta de cliente; l10n_ve_pos lo conserva para sus métodos.

function isCustomerRequired(order) {
    return Object.getOwnPropertyDescriptor(PosOrder.prototype, "isCustomerRequired").get.call(order);
}

function makeOrder({ partner = null, methods = [] }) {
    return {
        partner_id: partner,
        preset_id: null,
        isToInvoice: () => false,
        payment_ids: methods.map((method) => ({ payment_method_id: method })),
    };
}

describe("l10n_ve_pos isCustomerRequired", () => {
    test("un método de identificar cliente lo pide", () => {
        const order = makeOrder({ methods: [{ type: "bank", split_transactions: true }] });
        expect(isCustomerRequired(order)).toBe(true);
    });

    test("sin la bandera no lo pide", () => {
        const order = makeOrder({ methods: [{ type: "bank", split_transactions: false }] });
        expect(isCustomerRequired(order)).toBe(false);
    });

    test("con cliente ya no hace falta", () => {
        const order = makeOrder({
            partner: { id: 7 },
            methods: [{ type: "bank", split_transactions: true }],
        });
        expect(isCustomerRequired(order)).toBe(false);
    });

    test("el método de cuenta de cliente lo sigue pidiendo (core)", () => {
        const order = makeOrder({ methods: [{ type: "pay_later", split_transactions: false }] });
        expect(isCustomerRequired(order)).toBe(true);
    });
});
