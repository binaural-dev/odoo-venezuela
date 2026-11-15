import { test, expect, describe } from "@odoo/hoot";
import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import "@l10n_ve_pos/overrides/components/closing_popup/closing_popup";

// Odoo 20 keeps the closing note in the popup state and never sends it: the
// override sends it to the server before the core closes the session.

function makePopup({ notes, synced = false }) {
    const calls = [];
    const popup = {
        state: { notes },
        pos: {
            session: { id: 7 },
            accessRight: { forgetConnectedCashier: () => {} },
            pushOrdersWithClosingPopup: async () => synced,
            data: {
                call: async (...args) => {
                    calls.push(args);
                    return true;
                },
            },
        },
    };
    return { popup, calls };
}

describe("l10n_ve_pos closing note", () => {
    test("the note typed by the cashier goes to the server", async () => {
        const { popup, calls } = makePopup({ notes: "short by two bills" });
        await ClosePosPopup.prototype.closeSession.call(popup);
        expect(calls).toEqual([["pos.session", "update_closing_notes", [7, "short by two bills"]]]);
    });

    test("an empty note is sent too, so a cleared note is cleared", async () => {
        const { popup, calls } = makePopup({ notes: "" });
        await ClosePosPopup.prototype.closeSession.call(popup);
        expect(calls).toEqual([["pos.session", "update_closing_notes", [7, ""]]]);
    });
});
