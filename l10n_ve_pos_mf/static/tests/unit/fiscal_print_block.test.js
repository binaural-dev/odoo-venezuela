import { beforeEach, test, expect, describe } from "@odoo/hoot";
import { patchTranslations } from "@web/../tests/web_test_helpers";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import "@l10n_ve_pos_mf/overrides/OrderPaymentValidation";

beforeEach(() => patchTranslations());

function makeValidation({ fiscalMachine = true, mfInvoiceNumber = false, print } = {}) {
    const events = [];
    const order = { id: 1, uuid: "u1", totalDue: 10, mf_invoice_number: mfInvoiceNumber };
    const pos = {
        env: {
            services: {
                ui: {
                    block: (params) => events.push(`block:${params?.message || ""}`),
                    unblock: () => events.push("unblock"),
                },
            },
        },
        models: { "pos.order": { getBy: () => order } },
        dialog: { add: () => events.push("dialog") },
        useFiscalMachine: () => fiscalMachine,
        _applyGlobalDiscountBeforeValidation: () => {},
        pushToMF: async () => {
            events.push("print");
            return print();
        },
    };
    const validation = Object.create(OrderPaymentValidation.prototype);
    Object.assign(validation, { pos, orderUuid: order.uuid });
    return { validation, events };
}

describe("l10n_ve_pos_mf fiscal print feedback", () => {
    test("the UI is blocked with a message while the machine prints", async () => {
        const { validation, events } = makeValidation({ print: () => ({ valid: true }) });
        expect(await validation._mfPrintBeforeValidation()).toBe(true);
        expect(events).toEqual(["block:Imprimiendo en la máquina fiscal...", "print", "unblock"]);
    });

    test("the UI is unblocked when the print fails", async () => {
        const { validation, events } = makeValidation({ print: () => ({ valid: false }) });
        expect(await validation._mfPrintBeforeValidation()).toBe(false);
        expect(events).toEqual(["block:Imprimiendo en la máquina fiscal...", "print", "unblock"]);
    });

    test("the UI is unblocked when the print raises", async () => {
        const { validation, events } = makeValidation({
            print: () => {
                throw new Error("port closed");
            },
        });
        expect(await validation._mfPrintBeforeValidation()).toBe(false);
        expect(events).toEqual([
            "block:Imprimiendo en la máquina fiscal...",
            "print",
            "dialog",
            "unblock",
        ]);
    });

    test("nothing is blocked when there is nothing to print", async () => {
        const { validation, events } = makeValidation({ mfInvoiceNumber: "601" });
        expect(await validation._mfPrintBeforeValidation()).toBe(true);
        expect(events).toEqual([]);
    });
});
