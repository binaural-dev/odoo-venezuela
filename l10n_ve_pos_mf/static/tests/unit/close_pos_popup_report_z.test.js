import { describe, expect, test } from "@odoo/hoot";
import { AlertDialog, ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import "@l10n_ve_pos_mf/js/ClosePosPopup";
import { allowTranslations } from "@web/../tests/web_test_helpers";

// Ticket 16406: la caja lee S1 ANTES de imprimir la Z, como el flujo IoT. El
// contador de S1 es el de la última Z y el servidor le suma 1; leído después de
// imprimir, la sesión y las facturas quedaban con una Z de más (HKA80: imprimió
// la 0147 y la sesión guardó 148). Se prueba `_printFiscalReportZ` sobre el
// prototipo con un `this` falso (máquina fiscal, ORM y diálogos simulados).

allowTranslations();

const S1_OK = {
    success: true,
    data: { registeredMachineNumber: "Z7C0000001", dailyClosureCounter: 146 },
};

/** `s1Throws` hace que la lectura de S1 lance; `ormError` hace fallar el ORM. */
function fakePopup({
    z = { success: true },
    s1 = S1_OK,
    s1Throws = false,
    confirm = true,
    ormError = null,
} = {}) {
    const calls = [];
    const dialogs = [];
    const popup = Object.create(ClosePosPopup.prototype);
    popup.mfState = { isPrintingReport: false };
    popup.pos = { config: { serial_machine: "Z7C0000001" }, session: { id: 7 } };
    popup.getFiscalPrinter = () => ({
        isConnected: true,
        async _readS1Data() {
            calls.push("S1");
            if (s1Throws) {
                throw new Error("timeout del puerto");
            }
            return s1;
        },
        async printReportZ() {
            calls.push("Z");
            return z;
        },
    });
    popup.dialog = {
        add(component, props) {
            dialogs.push({ component, props });
            if (component === ConfirmationDialog) {
                return confirm ? props.confirm() : props.cancel();
            }
        },
    };
    popup.orm = {
        async call(model, method, args) {
            calls.push([model, method, args]);
            if (ormError) {
                throw new Error(ormError);
            }
        },
    };
    const alerts = () => dialogs.filter((d) => d.component === AlertDialog);
    return { popup, calls, alerts };
}

describe("ClosePosPopup._printFiscalReportZ", () => {
    test("lee S1 antes de la Z y sincroniza el contador de la última Z", async () => {
        const { popup, calls, alerts } = fakePopup();

        const ok = await popup._printFiscalReportZ();

        expect(ok).toBe(true);
        const value = {
            valid: true,
            data: { _registeredMachineNumber: "Z7C0000001", _dailyClosureCounter: 146 },
        };
        expect(calls).toEqual([
            "S1",
            "Z",
            ["account.move", "report_z", [[], "Z7C0000001", value]],
            ["pos.session", "set_report_z", [[7], value]],
        ]);
        expect(alerts().length).toBe(0);
        expect(popup.mfState.isPrintingReport).toBe(false);
    });

    test("sin S1 legible no imprime la Z ni sincroniza", async () => {
        const { popup, calls, alerts } = fakePopup({ s1: { success: false, data: null } });

        const ok = await popup._printFiscalReportZ();

        expect(ok).toBe(false);
        expect(calls).toEqual(["S1"]);
        expect(String(alerts()[0].props.title)).toBe("No se imprimio el Reporte Z");
        expect(popup.mfState.isPrintingReport).toBe(false);
    });

    test("S1 sin contador de Z: tampoco imprime", async () => {
        const { popup, calls } = fakePopup({
            s1: { success: true, data: { registeredMachineNumber: "Z7C0000001" } },
        });

        expect(await popup._printFiscalReportZ()).toBe(false);
        expect(calls).toEqual(["S1"]);
    });

    test("si la Z falla, no sincroniza", async () => {
        const { popup, calls, alerts } = fakePopup({ z: { success: false, error: "NAK" } });

        const ok = await popup._printFiscalReportZ();

        expect(ok).toBe(false);
        expect(calls).toEqual(["S1", "Z"]);
        expect(String(alerts()[0].props.title)).toBe("Error al imprimir Reporte Z");
    });

    test("si leer S1 lanza un error, no imprime la Z", async () => {
        const { popup, calls, alerts } = fakePopup({ s1Throws: true });

        expect(await popup._printFiscalReportZ()).toBe(false);
        expect(calls).toEqual(["S1"]);
        expect(String(alerts()[0].props.title)).toBe("Error al imprimir Reporte Z");
    });

    test("si Odoo falla tras imprimir la Z, avisa que no la repita", async () => {
        const { popup, calls, alerts } = fakePopup({ ormError: "sin conexión" });

        expect(await popup._printFiscalReportZ()).toBe(false);
        expect(calls.slice(0, 2)).toEqual(["S1", "Z"]);
        expect(String(alerts()[0].props.title)).toBe("Reporte Z impreso con advertencia");
        expect(String(alerts()[0].props.body)).toInclude("no repitas la Z");
        expect(String(alerts()[0].props.body)).toInclude("sin conexión");
    });

    test("si no confirma, no lee la máquina", async () => {
        const { popup, calls } = fakePopup({ confirm: false });

        expect(await popup._printFiscalReportZ()).toBe(false);
        expect(calls).toEqual([]);
    });
});
