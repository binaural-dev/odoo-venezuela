import { describe, expect, test } from "@odoo/hoot";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { browser } from "@web/core/browser/browser";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";
import { KioskDebugDialog } from "@l10n_ve_pos_self_order/app/debug/kiosk_debug_dialog";
import { KioskOrdersDialog } from "@l10n_ve_pos_self_order/app/debug/kiosk_orders_dialog";
import "@l10n_ve_pos_mf_self_order/overrides/self_order_fiscal";
import { POS_MENU_URL } from "@l10n_ve_pos_mf_self_order/app/debug/kiosk_debug_dialog_fiscal";
import { allowTranslations, patchWithCleanup } from "@web/../tests/web_test_helpers";

// Ticket 16406: "Cerrar sesión e imprimir Z" en el panel de Debug del Kiosko.
// Se prueban los métodos parcheados sobre el prototipo con un `this` falso
// (máquina fiscal, servidor y servicio de diálogos simulados), sin montar el
// Kiosko: el orden de los pasos y dónde se corta el flujo, como en la caja.

// Los mensajes del panel se leen con String(): necesita traducciones "cargadas".
allowTranslations();

const S1_OK = {
    success: true,
    data: { registeredMachineNumber: "Z7C0000001", dailyClosureCounter: 18 },
};

function fakePrinter({ z = { success: true }, s1 = S1_OK, throwOnZ = false } = {}) {
    const calls = [];
    return {
        calls,
        isConnected: true,
        async printReportZ() {
            calls.push("Z");
            if (throwOnZ) {
                throw new Error("puerto caído");
            }
            return z;
        },
        async _readS1Data() {
            calls.push("S1");
            return s1;
        },
    };
}

function fakeKioskService(printer) {
    const released = [];
    const service = Object.create(SelfOrder.prototype);
    service.ensureFiscalPrinterConnected = async () => printer;
    service._releaseFiscalPrinterConnection = async (p) => released.push(p);
    return { service, released };
}

describe("printKioskReportZ", () => {
    test("lee S1 antes de la Z y arma el valor que sincroniza la caja", async () => {
        const printer = fakePrinter();
        const { service, released } = fakeKioskService(printer);

        const result = await service.printKioskReportZ();

        expect(result.success).toBe(true);
        // El contador es el de la última Z (leído antes de imprimir): el
        // servidor le suma 1, como en el flujo IoT.
        expect(result.value).toEqual({
            valid: true,
            data: { _registeredMachineNumber: "Z7C0000001", _dailyClosureCounter: 18 },
        });
        expect(printer.calls).toEqual(["S1", "Z"]);
        expect(released.length).toBe(1);
    });

    test("sin máquina conectada no intenta imprimir", async () => {
        const { service } = fakeKioskService(null);

        const result = await service.printKioskReportZ();

        expect(result.success).toBe(false);
    });

    test("sin S1 legible no imprime la Z y libera el puerto", async () => {
        const printer = fakePrinter({ s1: { success: false, data: null } });
        const { service, released } = fakeKioskService(printer);

        const result = await service.printKioskReportZ();

        expect(result.success).toBe(false);
        expect(String(result.error)).toInclude("was not printed");
        expect(printer.calls).toEqual(["S1"]);
        expect(released.length).toBe(1);
    });

    test("S1 sin contador de Z: tampoco imprime", async () => {
        const printer = fakePrinter({
            s1: { success: true, data: { registeredMachineNumber: "Z7C0000001" } },
        });
        const { service } = fakeKioskService(printer);

        const result = await service.printKioskReportZ();

        expect(result.success).toBe(false);
        expect(printer.calls).toEqual(["S1"]);
    });

    test("si la Z falla, devuelve el error y libera el puerto", async () => {
        const printer = fakePrinter({ z: { success: false, error: "NAK" } });
        const { service, released } = fakeKioskService(printer);

        const result = await service.printKioskReportZ();

        expect(result).toEqual({ success: false, error: "NAK" });
        expect(printer.calls).toEqual(["S1", "Z"]);
        expect(released.length).toBe(1);
    });

    test("un error del driver no deja el puerto tomado", async () => {
        const printer = fakePrinter({ throwOnZ: true });
        const { service, released } = fakeKioskService(printer);

        const result = await service.printKioskReportZ();

        expect(result.success).toBe(false);
        expect(result.error).toBe("puerto caído");
        expect(released.length).toBe(1);
    });
});

function fakePanel({
    pending = [],
    reportZ = false,
    printing = false,
    confirm = true,
    z = { success: true, value: { valid: true, data: {} } },
    sync = { success: true },
    close = { success: true },
} = {}) {
    const calls = [];
    const dialogs = [];
    const panel = Object.create(KioskDebugDialog.prototype);
    panel.state = { busy: false, message: "", connected: null };
    panel.dialog = {
        add(component, props, options) {
            dialogs.push({ component, props });
            if (component === ConfirmationDialog) {
                calls.push("confirm");
                if (confirm) {
                    props.confirm();
                } else {
                    props.cancel();
                }
                options?.onClose?.();
            }
        },
    };
    panel.selfOrder = {
        isPrintingKioskFiscalInvoice: printing,
        async checkKioskCloseSession() {
            calls.push("check");
            return { pending_orders: pending, report_z: reportZ };
        },
        async printKioskReportZ() {
            calls.push("Z");
            return z;
        },
        async syncKioskReportZ(value) {
            calls.push(["sync", value]);
            return sync;
        },
        async closeKioskSession() {
            calls.push("close");
            return close;
        },
    };
    // `redirect` termina en `browser.location.assign`: se registra en vez de
    // navegar.
    patchWithCleanup(browser.location, {
        assign(url) {
            calls.push(["redirect", url]);
        },
    });
    const alerts = () => dialogs.filter((d) => d.component === AlertDialog);
    return { panel, calls, alerts, dialogs };
}

describe("isPrintingKioskFiscalInvoice", () => {
    test("refleja el overlay y las órdenes en impresión", () => {
        const service = Object.create(SelfOrder.prototype);
        service.printingFiscalInvoice = false;
        service._fiscalPrintingOrders = new Set();
        expect(service.isPrintingKioskFiscalInvoice).toBe(false);
        service._fiscalPrintingOrders.add("token");
        expect(service.isPrintingKioskFiscalInvoice).toBe(true);
        service._fiscalPrintingOrders.clear();
        service.printingFiscalInvoice = true;
        expect(service.isPrintingKioskFiscalInvoice).toBe(true);
    });
});

describe("onCloseSessionAndPrintZ", () => {
    test("flujo completo: pendientes, confirmación, Z, sincroniza, cierra y va al menú de cajas", async () => {
        const value = { valid: true, data: { _dailyClosureCounter: 18 } };
        const { panel, calls, alerts } = fakePanel({ z: { success: true, value } });

        await panel.onCloseSessionAndPrintZ();

        expect(calls.slice(0, -1)).toEqual(["check", "confirm", "Z", ["sync", value], "close"]);
        const [step, url] = calls.at(-1);
        expect(step).toBe("redirect");
        expect(new URL(url).pathname).toBe(POS_MENU_URL);
        expect(alerts().length).toBe(0);
        expect(String(panel.state.message)).toBe("Z report printed and session closed.");
        expect(panel.state.busy).toBe(false);
    });

    test("con órdenes sin número fiscal no imprime la Z ni cierra", async () => {
        const { panel, calls, alerts, dialogs } = fakePanel({
            pending: [
                { id: 1, name: "Orden 1", pos_reference: "Autopago CCCT 1 - 000010", state: "paid" },
                { id: 2, name: "Orden 2", pos_reference: "", state: "done" },
            ],
        });

        await panel.onCloseSessionAndPrintZ();

        expect(calls).toEqual(["check"]);
        expect(alerts().length).toBe(1);
        const alert = alerts()[0];
        const body = String(alert.props.body);
        expect(body).toInclude("Autopago CCCT 1 - 000010");
        expect(body).toInclude("Orden 2");
        // El aviso abre el panel de Órdenes para resolverlas.
        expect(String(alert.props.confirmLabel)).toBe("Open Orders");
        alert.props.confirm();
        expect(dialogs.at(-1).component).toBe(KioskOrdersDialog);
    });

    test("borrador con pago: remite al backend y no ofrece el panel", async () => {
        const { panel, calls, alerts } = fakePanel({
            pending: [{ id: 3, name: "Orden 3", pos_reference: "Autopago - 000011", state: "draft" }],
        });

        await panel.onCloseSessionAndPrintZ();

        expect(calls).toEqual(["check"]);
        const alert = alerts()[0];
        expect(String(alert.props.body)).toInclude(
            "Autopago - 000011 (unfinished order with a payment: resolve it from the backend)"
        );
        expect(alert.props.confirm).toBe(undefined);
    });

    test("si la sesión ya tiene su Z, no imprime otra", async () => {
        const { panel, calls, alerts } = fakePanel({ reportZ: "42" });

        await panel.onCloseSessionAndPrintZ();

        expect(calls).toEqual(["check"]);
        expect(String(alerts()[0].props.body)).toInclude("no. 42");
    });

    test("con una factura fiscal imprimiéndose no empieza", async () => {
        const { panel, calls, alerts } = fakePanel({ printing: true });

        await panel.onCloseSessionAndPrintZ();

        expect(calls).toEqual([]);
        expect(alerts().length).toBe(0);
        expect(String(panel.state.message)).toInclude("being printed");
    });

    test("si no confirma, no imprime la Z", async () => {
        const { panel, calls } = fakePanel({ confirm: false });

        await panel.onCloseSessionAndPrintZ();

        expect(calls).toEqual(["check", "confirm"]);
        expect(String(panel.state.message)).toBe("Cancelled.");
    });

    test("si la Z no sale (sin S1 o la máquina falla), no sincroniza ni cierra", async () => {
        const { panel, calls, alerts } = fakePanel({
            z: { success: false, error: "NAK" },
        });

        await panel.onCloseSessionAndPrintZ();

        expect(calls).toEqual(["check", "confirm", "Z"]);
        expect(String(alerts()[0].props.title)).toBe("Error printing the Z report");
        expect(String(alerts()[0].props.body)).toBe("NAK");
    });

    test("si Odoo no sincroniza la Z, no cierra la sesión", async () => {
        const { panel, calls, alerts } = fakePanel({
            sync: { success: false, error: "sin permisos" },
        });

        await panel.onCloseSessionAndPrintZ();

        expect(calls.at(-1)[0]).toBe("sync");
        expect(calls).not.toInclude("close");
        expect(String(alerts()[0].props.title)).toBe("Z report printed with a warning");
        expect(String(alerts()[0].props.body)).toInclude("sin permisos");
    });

    test("si el cierre falla, lo avisa", async () => {
        const { panel, calls, alerts } = fakePanel({
            close: { success: false, error: "diferencia de caja" },
        });

        await panel.onCloseSessionAndPrintZ();

        // Sin cierre no se sale del Kiosko.
        expect(calls.at(-1)).toBe("close");
        expect(String(alerts()[0].props.title)).toBe("Session not closed");
        expect(String(alerts()[0].props.body)).toInclude("diferencia de caja");
    });
});
