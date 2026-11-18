import { beforeEach, describe, expect, test } from "@odoo/hoot";
import { allowTranslations, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { session } from "@web/session";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import OrderPaymentValidation from "@point_of_sale/app/utils/order_payment_validation";
import "@l10n_ve_pos_mf/overrides/PosStore";
import "@l10n_ve_pos_mf/overrides/OrderPaymentValidation";
import { PrintVerificationQueue } from "@l10n_ve_pos_mf/utils/PrintVerificationQueue";

// Tarea 85447.
// 1. Un método con código fiscal de divisa (20-24) sin apply_igtf hace que la
//    máquina anule la factura (Flag 50 = 00): get_data_invoice corta antes de
//    hablar con la máquina.
// 2. Si la impresión falla, la venta sigue: la orden se sincroniza sin número
//    fiscal (pendiente por facturar). Si el driver no supo si la máquina la
//    emitió (`printed: null`), queda "por verificar" y se resuelve con la
//    máquina antes de imprimir el siguiente documento.
//
// Con la localización instalada Hoot no puede montar el PdV (ver
// definePosModels), así que se usa un `this` hecho a mano.

const USD_NO_IGTF = { name: "EFECTIVO USD", code_fiscal_printer: "20", apply_igtf: false };
const USD_IGTF = { name: "EFECTIVO USD IGTF", code_fiscal_printer: "20", apply_igtf: true };
const BS_CASH = { name: "EFECTIVO BS", code_fiscal_printer: "01", apply_igtf: false };
const PRINT_OK = { success: true, invoiceNumber: "00000001", serial: "Z1A", reportZ: "1" };
const VERIFICATION = {
    docType: "invoice",
    before: { number: 526, salesSubtotal: "2400", dailyClosureCounter: 137, serial: "Z1A" },
    paymentSent: true,
    closeAcked: true,
};

// Objeto sobre `proto` con propiedades propias, que tapan sus getters
// (`PosStore.company`, `OrderPaymentValidation.order`, ...).
function withOwn(proto, own) {
    return Object.create(
        proto,
        Object.fromEntries(
            Object.entries(own).map(([key, value]) => [key, { value, writable: true }])
        )
    );
}

function makeStore({
    connected = true,
    printResponse = PRINT_OK,
    verifyResponse = null,
    verify = null,
    orders = [],
    rpc = async () => true,
} = {}) {
    const calls = [];
    const printed = [];
    const dialogs = [];
    const synced = [];
    const store = withOwn(PosStore.prototype, {
        company: { name: "Test VE" },
        currency: { name: "VEF", decimal_places: 2, rounding: 0.01, isZero: (value) => value === 0 },
        config: { flag_21: "00", traditional_line: false, has_cashbox: false, seller_required: false },
        numberBuffer: { capture: () => {} },
        models: { "pos.order": { getBy: (field, value) => orders.find((o) => o[field] === value) } },
        data: {
            localUnsyncedPaidOrderUuids: new Set(),
            call: async (...args) => {
                calls.push(["rpc", ...args]);
                return rpc(...args);
            },
        },
        hardwareProxy: { openCashbox: () => {} },
        addPendingOrder: () => {},
        syncAllOrders: async () => {
            synced.push(true);
            return false;
        },
        aditionalInfo: () => [],
        _convertOrderForDriver: (order, data) => ({ payment_lines: data.payment_lines }),
        _mfShowError: (title, body) => dialogs.push(String(body)),
        dialog: { add: (component, props) => dialogs.push(String(props?.body)) },
        getFiscalPrinter: () => ({
            isConnected: connected,
            printInvoice: async (driverOrder) => {
                calls.push(["printInvoice", driverOrder]);
                printed.push(driverOrder);
                return printResponse;
            },
            verifyDocument: async (verification) => {
                calls.push(["verifyDocument", verification]);
                return verify ? verify(verification) : verifyResponse;
            },
        }),
    });
    return { store, calls, printed, dialogs, synced };
}

function makeOrder(payments, values = {}) {
    return {
        id: 1,
        uuid: "order-85447",
        pos_reference: "Orden 85447",
        state: "draft",
        totalDue: 100,
        change: 0,
        getPartner: () => null,
        isPaidWithCash: () => false,
        lines: [
            {
                price_unit: 100,
                qty: 1,
                getDiscount: () => 0,
                tax_ids: [],
                product_id: { display_name: "Producto", default_code: "P1" },
                refunded_orderline_id: false,
            },
        ],
        payment_ids: payments.map(([method, amount]) => ({
            amount,
            payment_method_id: method,
        })),
        ...values,
    };
}

function makeValidation(store, order) {
    return withOwn(OrderPaymentValidation.prototype, { pos: store, order });
}

beforeEach(() => {
    localStorage.removeItem(PrintVerificationQueue.STORAGE_KEY);
});

describe("l10n_ve_pos_mf la venta sigue si la máquina fiscal falla", () => {
    test("una falla de la máquina deja la orden pendiente y se sincroniza", async () => {
        allowTranslations();
        const failure = { success: false, printed: false, error: "FACTURA ANULADA" };
        const { store, dialogs, synced } = makeStore({ printResponse: failure });
        const order = makeOrder([[BS_CASH, 100]]);

        await makeValidation(store, order).finalizeValidation();

        expect(dialogs).toEqual(["FACTURA ANULADA"]);
        expect(synced.length).toBe(1);
        expect(order.state).toBe("paid");
        expect(order.mf_invoice_number).toBe(undefined);
        expect(order.mf_print_verification).toBe(undefined);
        expect(PrintVerificationQueue.getAll()).toEqual([]);
    });

    test("si no se sabe si se imprimió, la orden queda por verificar", async () => {
        allowTranslations();
        const unknown = {
            success: false,
            printed: null,
            verification: VERIFICATION,
            error: "No se pudo confirmar",
        };
        const { store, synced } = makeStore({ printResponse: unknown });
        const order = makeOrder([[BS_CASH, 100]]);

        await makeValidation(store, order).finalizeValidation();

        expect(synced.length).toBe(1);
        expect(order.mf_print_verification).toEqual(VERIFICATION);
        expect(PrintVerificationQueue.getAll().map((entry) => entry.uuid)).toEqual(["order-85447"]);
    });

    test("con la impresión exitosa la orden sale con su número", async () => {
        allowTranslations();
        const { store, synced } = makeStore();
        const order = makeOrder([[BS_CASH, 100]]);

        await makeValidation(store, order).finalizeValidation();

        expect(order.mf_invoice_number).toBe("00000001");
        expect(synced.length).toBe(1);
    });
});

describe("l10n_ve_pos_mf pedidos por verificar", () => {
    function queuePrevious() {
        const previous = { uuid: "prev", pos_reference: "Orden previa", mf_print_verification: VERIFICATION };
        PrintVerificationQueue.add("prev", VERIFICATION);
        return previous;
    }

    test("antes de imprimir se resuelve el pedido por verificar con la máquina", async () => {
        allowTranslations();
        const previous = queuePrevious();
        const verified = { success: true, printed: true, invoiceNumber: "527", serial: "Z1A", reportZ: 138 };
        const { store, calls } = makeStore({ verifyResponse: verified, orders: [previous] });

        await store.pushToMF(makeOrder([[BS_CASH, 100]]));

        expect(calls.map(([name]) => name)).toEqual(["verifyDocument", "rpc", "printInvoice"]);
        expect(calls[1].slice(1)).toEqual([
            "pos.order",
            "mf_resolve_print_verification",
            ["prev", { printed: true, invoiceNumber: "527", serial: "Z1A", reportZ: 138 }],
        ]);
        expect(previous.mf_invoice_number).toBe("527");
        expect(previous.mf_print_verification).toBe(false);
        expect(PrintVerificationQueue.getAll()).toEqual([]);
    });

    test("si la máquina dice que no se imprimió, el pedido pasa a pendiente", async () => {
        allowTranslations();
        const previous = queuePrevious();
        const { store } = makeStore({ verifyResponse: { success: false, printed: false }, orders: [previous] });

        await store.pushToMF(makeOrder([[BS_CASH, 100]]));

        expect(previous.mf_invoice_number).toBe(undefined);
        expect(previous.mf_print_verification).toBe(false);
        expect(PrintVerificationQueue.getAll()).toEqual([]);
    });

    test("lo que no se puede resolver queda para revisión manual y no frena la venta", async () => {
        allowTranslations();
        const previous = queuePrevious();
        const { store, calls, dialogs } = makeStore({
            verifyResponse: { success: false, printed: null, reason: "unattributable" },
            orders: [previous],
        });

        const result = await store.pushToMF(makeOrder([[BS_CASH, 100]]));

        expect(result.valid).toBe(true);
        expect(calls.map(([name]) => name)).toEqual(["verifyDocument", "printInvoice"]);
        expect(dialogs.length).toBe(1);
        expect(dialogs[0]).toInclude("Orden previa");
        expect(previous.mf_print_verification).toEqual(VERIFICATION);
        expect(PrintVerificationQueue.getAll()).toEqual([]);
    });

    test("sin servidor el resultado se guarda y se reintenta sin volver a verificar", async () => {
        allowTranslations();
        queuePrevious();
        let online = false;
        const verified = { success: true, printed: true, invoiceNumber: "527", serial: "Z1A", reportZ: 138 };
        const { store, calls } = makeStore({
            verifyResponse: verified,
            rpc: async () => {
                if (!online) {
                    throw new Error("offline");
                }
                return true;
            },
        });

        await store._mfResolvePrintVerifications();
        expect(PrintVerificationQueue.getAll()[0].resolved.invoiceNumber).toBe("527");

        online = true;
        await store._mfResolvePrintVerifications();
        expect(calls.filter(([name]) => name === "verifyDocument").length).toBe(1);
        expect(PrintVerificationQueue.getAll()).toEqual([]);
    });
});

describe("l10n_ve_pos_mf volver a validar no reimprime", () => {
    // Si el servidor rechaza la sincronización, el core deja la orden en
    // borrador en la pantalla de pago y el cajero puede volver a validarla.
    function flaggedOrder() {
        const order = makeOrder([[BS_CASH, 100]], { mf_print_verification: VERIFICATION });
        PrintVerificationQueue.add(order.uuid, VERIFICATION);
        return order;
    }

    test("un pedido por verificar que la máquina emitió recibe su número sin reimprimirse", async () => {
        allowTranslations();
        const order = flaggedOrder();
        const verified = { success: true, printed: true, invoiceNumber: "527", serial: "Z1A", reportZ: 138 };
        const { store, calls, synced } = makeStore({ verifyResponse: verified, orders: [order] });

        await makeValidation(store, order).finalizeValidation();

        expect(calls.map(([name]) => name)).toEqual(["verifyDocument", "rpc"]);
        expect(order.mf_invoice_number).toBe("527");
        expect(order.mf_print_verification).toBe(false);
        expect(synced.length).toBe(1);
    });

    test("un pedido por verificar sin resolver no se reimprime y se sincroniza pendiente", async () => {
        allowTranslations();
        const order = flaggedOrder();
        const { store, printed, dialogs, synced } = makeStore({
            verifyResponse: { success: false, printed: null, reason: "unattributable" },
            orders: [order],
        });

        await makeValidation(store, order).finalizeValidation();

        expect(printed).toEqual([]);
        expect(order.mf_invoice_number).toBe(undefined);
        expect(order.mf_print_verification).toEqual(VERIFICATION);
        expect(dialogs.length).toBe(2);
        expect(synced.length).toBe(1);
        expect(order.state).toBe("paid");
    });

    test("un pedido por verificar que la máquina no emitió se imprime al volver a validar", async () => {
        allowTranslations();
        const order = flaggedOrder();
        const { store, printed } = makeStore({
            verifyResponse: { success: false, printed: false },
            orders: [order],
        });

        await makeValidation(store, order).finalizeValidation();

        expect(printed.length).toBe(1);
        expect(order.mf_invoice_number).toBe("00000001");
        expect(order.mf_print_verification).toBe(false);
    });
});

describe("l10n_ve_pos_mf cola de verificación", () => {
    function queuePrevious() {
        const previous = { uuid: "prev", pos_reference: "Orden previa", mf_print_verification: VERIFICATION };
        PrintVerificationQueue.add("prev", VERIFICATION);
        return previous;
    }

    test("si la máquina no responde al verificar, la venta queda pendiente y el pedido sigue en la cola", async () => {
        allowTranslations();
        const previous = queuePrevious();
        const { store, printed, dialogs, synced } = makeStore({
            verifyResponse: { success: false, printed: null, reason: "no_response" },
            orders: [previous],
        });
        const order = makeOrder([[BS_CASH, 100]]);

        await makeValidation(store, order).finalizeValidation();

        expect(printed).toEqual([]);
        expect(dialogs.length).toBe(1);
        expect(synced.length).toBe(1);
        expect(order.state).toBe("paid");
        expect(order.mf_invoice_number).toBe(undefined);
        expect(PrintVerificationQueue.getAll().map((entry) => entry.uuid)).toEqual(["prev"]);
        expect(previous.mf_print_verification).toEqual(VERIFICATION);
    });

    test("con una NC abierta que no se pudo cerrar, la venta queda pendiente y se pide reiniciar", async () => {
        allowTranslations();
        const previous = queuePrevious();
        const { store, printed, dialogs, synced } = makeStore({
            verifyResponse: { success: false, printed: null, reason: "document_open" },
            orders: [previous],
        });
        const order = makeOrder([[BS_CASH, 100]]);

        await makeValidation(store, order).finalizeValidation();

        expect(printed).toEqual([]);
        expect(synced.length).toBe(1);
        expect(dialogs.length).toBe(1);
        expect(dialogs[0]).toInclude("Restart the fiscal printer");
        expect(PrintVerificationQueue.getAll().map((entry) => entry.uuid)).toEqual(["prev"]);
        expect(previous.mf_print_verification).toEqual(VERIFICATION);
    });

    test("con otra máquina conectada el pedido sigue en la cola y la venta se imprime", async () => {
        allowTranslations();
        const previous = queuePrevious();
        const { store, printed, dialogs } = makeStore({
            verifyResponse: { success: false, printed: null, reason: "other_printer" },
            orders: [previous],
        });

        const result = await store.pushToMF(makeOrder([[BS_CASH, 100]]));

        expect(result.valid).toBe(true);
        expect(printed.length).toBe(1);
        expect(dialogs).toEqual([]);
        expect(PrintVerificationQueue.getAll().map((entry) => entry.uuid)).toEqual(["prev"]);
    });

    test("si la verificación falla, el pedido pasa a revisión manual y la venta se imprime", async () => {
        allowTranslations();
        const previous = queuePrevious();
        const { store, printed, dialogs } = makeStore({
            verify: async () => {
                throw new Error("port lost");
            },
            orders: [previous],
        });

        const result = await store.pushToMF(makeOrder([[BS_CASH, 100]]));

        expect(result.valid).toBe(true);
        expect(printed.length).toBe(1);
        expect(dialogs.length).toBe(1);
        expect(dialogs[0]).toInclude("Orden previa");
        expect(PrintVerificationQueue.getAll()).toEqual([]);
    });

    test("una entrada dañada de la cola se descarta sin frenar la venta", async () => {
        allowTranslations();
        localStorage.setItem(
            PrintVerificationQueue.STORAGE_KEY,
            JSON.stringify([{ uuid: "broken" }, null])
        );
        const { store, calls, printed } = makeStore();

        const result = await store.pushToMF(makeOrder([[BS_CASH, 100]]));

        expect(result.valid).toBe(true);
        expect(printed.length).toBe(1);
        expect(calls.filter(([name]) => name === "verifyDocument")).toEqual([]);
        expect(PrintVerificationQueue.getAll()).toEqual([]);
    });

    test("dos resoluciones a la vez consultan la máquina una sola vez", async () => {
        allowTranslations();
        queuePrevious();
        const verified = { success: true, printed: true, invoiceNumber: "527", serial: "Z1A", reportZ: 138 };
        const { store, calls } = makeStore({
            verify: async () => {
                await new Promise((resolve) => setTimeout(resolve, 10));
                return verified;
            },
        });

        const results = await Promise.all([
            store._mfResolvePrintVerifications(),
            store._mfResolvePrintVerifications(),
        ]);

        expect(results).toEqual([true, true]);
        expect(calls.filter(([name]) => name === "verifyDocument").length).toBe(1);
        expect(PrintVerificationQueue.getAll()).toEqual([]);
    });

    test("cada base de datos tiene su propia cola", () => {
        patchWithCleanup(session, { db: "base_a" });
        PrintVerificationQueue.add("order-a", VERIFICATION);
        expect(PrintVerificationQueue.STORAGE_KEY).toBe("l10n_ve_pos_mf_print_verifications:base_a");

        patchWithCleanup(session, { db: "base_b" });
        expect(PrintVerificationQueue.getAll()).toEqual([]);

        patchWithCleanup(session, { db: "base_a" });
        expect(PrintVerificationQueue.getAll().map((entry) => entry.uuid)).toEqual(["order-a"]);
        PrintVerificationQueue.remove("order-a");
    });
});

describe("l10n_ve_pos_mf código fiscal de divisa sin IGTF", () => {
    test("pushToMF no llama al driver con un pago 20 sin IGTF", async () => {
        allowTranslations();
        const { store, printed, dialogs } = makeStore();
        const order = makeOrder([
            [USD_NO_IGTF, 40],
            [BS_CASH, 60],
        ]);

        const result = await store.pushToMF(order);

        expect(result.valid).toBe(false);
        expect(printed).toEqual([]);
        expect(dialogs.length).toBe(1);
        expect(dialogs[0]).toInclude("EFECTIVO USD");
        expect(order.mf_invoice_number).toBe(undefined);
    });

    test("sin l10n_ve_pos_igtf (apply_igtf undefined) también bloquea", async () => {
        allowTranslations();
        const { store } = makeStore();
        const method = { name: "EFECTIVO USD", code_fiscal_printer: "22" };
        const data = await store.get_data_invoice(makeOrder([[method, 100]]));

        expect(data.valid).toBe(false);
        expect(String(data.message)).toInclude("EFECTIVO USD");
    });

    test("con IGTF activo el código 20 llega a la máquina como hasta ahora", async () => {
        allowTranslations();
        const { store, printed, dialogs } = makeStore();
        const order = makeOrder([
            [USD_IGTF, 40],
            [BS_CASH, 60],
        ]);

        const result = await store.pushToMF(order);

        expect(result.valid).toBe(true);
        expect(dialogs).toEqual([]);
        expect(printed.length).toBe(1);
        expect(printed[0].payment_lines.map((line) => line.payment_method)).toEqual([
            "20",
            "01",
        ]);
        expect(order.mf_invoice_number).toBe("00000001");
    });

    test("un pago en cero o un vuelto con ese método no cuentan", async () => {
        allowTranslations();
        const { store } = makeStore();
        const zero = await store.get_data_invoice(
            makeOrder([
                [USD_NO_IGTF, 0],
                [BS_CASH, 100],
            ])
        );
        expect(zero.valid).toBe(true);
        expect(zero.payment_lines).toEqual([{ payment_method: "01", amount: 100 }]);

        const change = makeOrder([
            [BS_CASH, 120],
            [USD_NO_IGTF, -20],
        ]);
        expect(store._mfFindForeignCodeWithoutIgtfPayment(change)).toBe(undefined);
    });

    test("en una nota de crédito cuenta el pago negativo", () => {
        const { store } = makeStore();
        const refund = makeOrder([[USD_NO_IGTF, -100]], { totalDue: -100 });
        expect(store._mfFindForeignCodeWithoutIgtfPayment(refund)?.payment_method_id).toBe(
            USD_NO_IGTF
        );
    });

    test("los códigos nacionales y el '2' sin cero no se bloquean", () => {
        const { store } = makeStore();
        for (const code of ["01", "2", "02", "15", "19", "25", "", false, undefined]) {
            expect(
                store._mfIsForeignCodeWithoutIgtf({ code_fiscal_printer: code, apply_igtf: false })
            ).toBe(false);
        }
        for (const code of ["20", "21", "22", "23", "24", " 20"]) {
            expect(
                store._mfIsForeignCodeWithoutIgtf({ code_fiscal_printer: code, apply_igtf: false })
            ).toBe(true);
            expect(
                store._mfIsForeignCodeWithoutIgtf({ code_fiscal_printer: code, apply_igtf: true })
            ).toBe(false);
        }
    });
});

describe("l10n_ve_pos_mf divisa sin IGTF en la pantalla de pago", () => {
    // Pedido que pasa los chequeos de isOrderValid del core (y de otros
    // módulos que lo extienden, como el vendedor de binaural_pos_seller).
    function makeValidOrder(payments) {
        return makeOrder(payments, {
            seller_id: { id: 7 },
            priceIncl: 100,
            amountPaid: 100,
            appliedRounding: 0,
            presetRequirementsFilled: true,
            getOrderlines() {
                return this.lines;
            },
            isRefundInProcess: () => false,
            isToInvoice: () => false,
            getShippingDate: () => false,
            isPaid: () => true,
            _isValidEmptyOrder: () => true,
        });
    }

    function makeCoreValidation(store, order, own = {}) {
        return withOwn(OrderPaymentValidation.prototype, {
            pos: store,
            order,
            invoicing: false,
            payment_methods_from_config: [],
            isInvoiceRequired: () => false,
            ...own,
        });
    }

    test("un pago 20 sin IGTF deja al cajero en la pantalla de pago", async () => {
        allowTranslations();
        const { store, dialogs, printed } = makeStore();
        const order = makeValidOrder([
            [USD_NO_IGTF, 40],
            [BS_CASH, 60],
        ]);

        expect(await makeCoreValidation(store, order).isOrderValid()).toBe(false);

        expect(dialogs.length).toBe(1);
        expect(dialogs[0]).toInclude("EFECTIVO USD");
        expect(printed).toEqual([]);
    });

    test("validateOrder no llega a imprimir ni a sincronizar", async () => {
        allowTranslations();
        const { store, dialogs } = makeStore();
        const order = makeValidOrder([[USD_NO_IGTF, 100]]);
        const reached = [];
        const validation = makeCoreValidation(store, order, {
            askBeforeValidation: async () => true,
            checkCashRoundingHasBeenWellApplied: () => true,
            shouldHideValidationBehindFeedbackScreen: async () => reached.push("navigate"),
            finalizeValidation: async () => reached.push("finalize"),
        });

        await validation.validateOrder(false);

        // No llega a finalizeValidation (imprime y sincroniza) ni navega.
        expect(reached).toEqual([]);
        expect(dialogs.length).toBe(1);
    });

    test("una orden que no va a la máquina (gancho) no se bloquea ni se imprime", async () => {
        allowTranslations();
        const { store, dialogs, printed, synced } = makeStore();
        // Como hace binaural_operative_pos_mf con las órdenes operativas.
        store._mfOrderGoesToFiscalPrinter = () => false;
        const order = makeValidOrder([[USD_NO_IGTF, 100]]);

        expect(await makeCoreValidation(store, order).isOrderValid()).toBe(true);
        await makeValidation(store, order).finalizeValidation();

        expect(dialogs).toEqual([]);
        expect(printed).toEqual([]);
        expect(synced.length).toBe(1);
    });

    test("con IGTF activo, o sin máquina fiscal conectada, la validación sigue", async () => {
        allowTranslations();
        const { store, dialogs } = makeStore();
        expect(await makeCoreValidation(store, makeValidOrder([[USD_IGTF, 100]])).isOrderValid()).toBe(
            true
        );

        // Sin máquina no se imprime: la orden queda pendiente y el bloqueo de
        // get_data_invoice la frena al imprimirla después.
        const offline = makeStore({ connected: false });
        expect(
            await makeCoreValidation(offline.store, makeValidOrder([[USD_NO_IGTF, 100]])).isOrderValid()
        ).toBe(true);

        expect(dialogs).toEqual([]);
        expect(offline.dialogs).toEqual([]);
    });
});

describe("l10n_ve_pos_mf error inesperado al imprimir", () => {
    test("se avisa al cajero y la orden queda pendiente", async () => {
        allowTranslations();
        const { store, dialogs, synced, printed } = makeStore();
        store._convertOrderForDriver = () => {
            throw new TypeError("payload roto");
        };
        const order = makeOrder([[BS_CASH, 100]]);

        await makeValidation(store, order).finalizeValidation();

        expect(dialogs.length).toBe(1);
        expect(dialogs[0]).toInclude("payload roto");
        expect(printed).toEqual([]);
        expect(synced.length).toBe(1);
        expect(order.mf_invoice_number).toBe(undefined);
    });
});
