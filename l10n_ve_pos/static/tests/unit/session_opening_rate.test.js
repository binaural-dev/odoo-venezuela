import { test, expect, describe } from "@odoo/hoot";
import { allowTranslations, patchWithCleanup } from "@web/../tests/web_test_helpers";
import { localization } from "@web/core/l10n/localization";
import { ConnectionLostError, RPCError } from "@web/core/network/rpc";
import { PosStore } from "@point_of_sale/app/services/pos_store";
import { OpeningControlPopup } from "@point_of_sale/app/components/popups/opening_control_popup/opening_control_popup";
import "@l10n_ve_pos/overrides/services/pos_store";
import "@l10n_ve_pos/overrides/components/opening_control_popup/opening_control_popup";

const { DateTime } = luxon;

// Ticket 16351: la caja no abre con una tasa que no es la de la sesión y
// avisa cuando la sesión es de un día anterior (cobra con la tasa de ese día).

function makeStore({ result, error, session = {}, orders = [], readResult } = {}) {
    const calls = [];
    const dialogs = [];
    const reloads = [];
    const notifications = [];
    const store = {
        config: { foreign_inverse_rate: 1 / 40 },
        session: { id: 7, state: "opened", ...session },
        models: {
            "res.currency": {
                getAll: () => [
                    { id: 1, rate: 1 / 40 },
                    { id: 2, rate: 1 },
                ],
            },
            "pos.order": orders,
        },
        data: {
            call: async (model, method, args) => {
                calls.push({ model, method, args });
                if (error) {
                    throw error;
                }
                return method === "read" ? readResult : result;
            },
        },
        dialog: {
            add: (component, props, options) => {
                dialogs.push(props);
                options?.onClose?.();
            },
        },
        notification: { add: (message, options) => notifications.push({ message, options }) },
        reloadData: async (fullReload) => reloads.push(fullReload),
        reloadIfSessionDeleted: async (err) => {
            reloads.push("session-deleted");
            if (!(err instanceof RPCError)) {
                throw err;
            }
        },
    };
    for (const name of ["_getLoadedRates", "_sessionRateFromPreviousDayMessage"]) {
        store[name] = PosStore.prototype[name];
    }
    Object.defineProperty(
        store,
        "isSessionRateFromPreviousDay",
        Object.getOwnPropertyDescriptor(PosStore.prototype, "isSessionRateFromPreviousDay")
    );
    return { store, calls, dialogs, reloads, notifications };
}

const checkOpeningRate = (store) => PosStore.prototype.checkOpeningRate.call(store);

function makePopup(check) {
    const steps = [];
    const popup = {
        pos: {
            checkOpeningRate: async () => check,
            session: { id: 7, state: "opening_control" },
            data: {
                call: async (model, method) => {
                    steps.push(method);
                    popup.pos.session.state = "opened"; // como el servidor
                },
            },
            reloadData: async () => steps.push("reloadData"),
            loadSessionRateDate: async () => steps.push("loadSessionRateDate"),
            reloadIfSessionDeleted: (error) => {
                throw error;
            },
        },
        state: { openingCash: "0", notes: "" },
        props: { close: () => steps.push("close") },
        _beforeOpeningSession: async () => steps.push("_beforeOpeningSession"),
    };
    return { popup, steps };
}

describe("l10n_ve_pos tasa de apertura de la sesión", () => {
    test("manda al servidor las tasas que tiene cargadas el navegador", async () => {
        const { store, calls } = makeStore({ result: { status: "ok" } });
        expect(await checkOpeningRate(store)).toBe("ok");
        expect(calls).toEqual([
            {
                model: "pos.session",
                method: "check_opening_rate",
                args: [
                    7,
                    {
                        foreign_inverse_rate: 1 / 40,
                        currencies: { 1: 1 / 40, 2: 1 },
                        tender_currency_rates: {},
                    },
                ],
            },
        ]);
    });

    test("sin tasa del día la caja no abre y no recarga", async () => {
        allowTranslations();
        const { store, dialogs, reloads } = makeStore({
            result: { status: "missing", currency: "USD", date: "11/03/2026" },
        });
        expect(await checkOpeningRate(store)).toBe("blocked");
        expect(dialogs.length).toBe(1);
        expect(String(dialogs[0].body)).toInclude("11/03/2026");
        expect(reloads).toEqual([]);
    });

    test("con una tasa vieja avisa y recarga los datos completos", async () => {
        allowTranslations();
        const { store, dialogs, reloads } = makeStore({
            result: { status: "outdated", currency: "USD", rate: "41,0000", date: "11/03/2026" },
        });
        expect(await checkOpeningRate(store)).toBe("blocked");
        expect(String(dialogs[0].body)).toInclude("41,0000");
        expect(reloads).toEqual([true]);
    });

    test("tasa vieja con órdenes pagadas sin enviar: abre y recarga después", async () => {
        allowTranslations();
        const { store, dialogs, reloads } = makeStore({
            result: { status: "outdated", currency: "USD", rate: "41,0000", date: "11/03/2026" },
            orders: [{ isUnsyncedPaid: true, state: "paid" }],
        });
        expect(await checkOpeningRate(store)).toBe("reload");
        expect(String(dialogs[0].body)).toInclude("41,0000");
        expect(reloads).toEqual([]);
    });

    test("sin conexión deja que el core muestre su aviso", async () => {
        const { store, reloads } = makeStore({ error: new ConnectionLostError("/x") });
        expect(await checkOpeningRate(store)).toBe("ok");
        expect(reloads).toEqual([]);
    });

    test("sesión borrada: delega en la recarga del core", async () => {
        const { store, reloads } = makeStore({ error: new RPCError("MissingError") });
        expect(await checkOpeningRate(store)).toBe("blocked");
        expect(reloads).toEqual(["session-deleted"]);
    });

    test("el popup no abre ni registra nada si la tasa no es la de la sesión", async () => {
        const { popup, steps } = makePopup("blocked");
        await OpeningControlPopup.prototype.confirm.call(popup);
        expect(steps).toEqual([]);
    });

    test("el popup abre después del gancho y lee el día de la tasa", async () => {
        // parseFloat del monto de apertura usa la localización
        patchWithCleanup(localization, { decimalPoint: ",", thousandsSep: ".", grouping: [3, 0] });
        const { popup, steps } = makePopup("ok");
        await OpeningControlPopup.prototype.confirm.call(popup);
        expect(steps).toEqual([
            "_beforeOpeningSession",
            "set_opening_control",
            "close",
            "loadSessionRateDate",
        ]);
    });

    test("el popup abre y recarga cuando hay órdenes pagadas sin enviar", async () => {
        patchWithCleanup(localization, { decimalPoint: ",", thousandsSep: ".", grouping: [3, 0] });
        const { popup, steps } = makePopup("reload");
        await OpeningControlPopup.prototype.confirm.call(popup);
        expect(steps).toEqual(["_beforeOpeningSession", "set_opening_control", "close", "reloadData"]);
    });

    test("después de abrir, la sesión del navegador recibe el día de su tasa", async () => {
        const { store } = makeStore({ readResult: [{ id: 7, foreign_rate_date: "2026-11-12" }] });
        await PosStore.prototype.loadSessionRateDate.call(store);
        expect(store.session.foreign_rate_date.toISODate()).toBe("2026-11-12");
    });

    test("sesión de un día anterior: avisa sin bloquear", () => {
        patchWithCleanup(localization, { dateFormat: "dd/MM/yyyy" }); // formatDate
        allowTranslations();
        const yesterday = DateTime.now().minus({ days: 1 }).startOf("day");
        const { store, notifications } = makeStore({ session: { foreign_rate_date: yesterday } });
        expect(store.isSessionRateFromPreviousDay).toBe(true);
        PosStore.prototype._notifySessionRateFromPreviousDay.call(store);
        expect(notifications.length).toBe(1);
        expect(notifications[0].options).toEqual({ type: "warning" });
    });

    test("sesión de hoy, en apertura o sin tasa guardada: sin aviso", () => {
        const today = DateTime.now().startOf("day");
        const yesterday = today.minus({ days: 1 });
        expect(makeStore({ session: { foreign_rate_date: today } }).store.isSessionRateFromPreviousDay).toBe(false);
        expect(
            makeStore({ session: { foreign_rate_date: yesterday, state: "opening_control" } }).store
                .isSessionRateFromPreviousDay
        ).toBe(false);
        expect(makeStore().store.isSessionRateFromPreviousDay).toBe(false);
    });
});
