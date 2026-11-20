import { test, expect, describe } from "@odoo/hoot";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import "@l10n_ve_pos_mf/overrides/PosStore";

function makePos(extra = {}) {
    const calls = [];
    const pos = Object.create(PosStore.prototype);
    Object.defineProperty(pos, "config", { value: { has_cashbox: true, receipt_printer_ids: [] } });
    Object.assign(pos, {
        getFiscalPrinter: () => ({
            isConnected: true,
            openDrawer: async () => {
                calls.push("DRAWER");
                return { success: true };
            },
        }),
        ...extra,
    });
    return { pos, calls };
}

describe("l10n_ve_pos_mf fiscal drawer", () => {
    test("cash in/out opens the drawer through the fiscal machine", async () => {
        const { pos, calls } = makePos();
        await pos.openCashbox("Cash in / out");
        expect(calls).toEqual(["DRAWER"]);
    });

    test("validating an order does not send the drawer command", async () => {
        const { pos, calls } = makePos({ _mfValidatingOrder: { id: 1 } });
        await pos.openCashbox();
        expect(calls).toEqual([]);
    });

    test("the validation hook can ask for the fiscal drawer", async () => {
        const { pos, calls } = makePos({
            _mfValidatingOrder: { id: 1 },
            mfOpensDrawerOnValidation: () => true,
        });
        await pos.openCashbox();
        expect(calls).toEqual(["DRAWER"]);
    });
});
