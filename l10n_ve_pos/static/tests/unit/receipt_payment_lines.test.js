import { test, expect, describe } from "@odoo/hoot";
import { GeneratePrinterData } from "@point_of_sale/app/utils/printer/generate_printer_data";
import "@l10n_ve_pos/overrides/utils/generate_printer_data";

// A payment in a currency other than the register's prints the method name
// with the currency paid and the amount in the currency of the register.

const VEF = { id: 1, name: "VEF" };
const USD = { id: 2, name: "USD" };

function makePrinterData(payments) {
    return {
        order: { payment_ids: payments },
        formatCurrency: (amount, currency) => `${amount} ${currency.name}`,
    };
}

function makePayment({ method, amount, amountCurrency, currency, isChange = false }) {
    return {
        raw: { amount, amount_currency: amountCurrency },
        payment_method_id: { name: method },
        pos_order_id: { currency: VEF },
        currency,
        amount,
        amount_currency: amountCurrency,
        is_change: isChange,
        isDifferentCurrency: currency.id !== VEF.id,
        getAmount: () => amount,
    };
}

function generate(payments) {
    return GeneratePrinterData.prototype.generatePaymentData.call(makePrinterData(payments));
}

describe("l10n_ve_pos receipt payment lines", () => {
    test("a payment in the currency of the register prints as core", () => {
        const lines = generate([
            makePayment({ method: "TDD BNC", amount: 5000, amountCurrency: 0, currency: VEF }),
        ]);
        expect(lines[0].payment_method_data.name).toBe("TDD BNC");
        expect(lines[0].amount).toBe("5000 VEF");
    });

    test("a payment in another currency prints the currency paid and the amount in the register currency", () => {
        const lines = generate([
            makePayment({ method: "Efectivo Bs.", amount: 36106.2, amountCurrency: 100, currency: USD }),
        ]);
        expect(lines[0].payment_method_data.name).toBe("Efectivo Bs. (USD)");
        expect(lines[0].amount).toBe("36106.2 VEF");
    });

    test("any method follows the same rule", () => {
        const lines = generate([
            makePayment({ method: "ZELLE", amount: 3650, amountCurrency: 10, currency: USD }),
            makePayment({ method: "TDD BNC", amount: 5000, amountCurrency: 0, currency: VEF }),
        ]);
        expect(lines.map((line) => line.payment_method_data.name)).toEqual([
            "ZELLE (USD)",
            "TDD BNC",
        ]);
    });

    test("the payment that records the change is not a line", () => {
        const lines = generate([
            makePayment({ method: "Efectivo Bs.", amount: 55038.18, amountCurrency: 60, currency: USD }),
            makePayment({ method: "Efectivo Bs.", amount: -17848.79, amountCurrency: 0, currency: VEF, isChange: true }),
        ]);
        expect(lines.length).toBe(1);
        expect(lines[0].payment_method_data.name).toBe("Efectivo Bs. (USD)");
    });
});
