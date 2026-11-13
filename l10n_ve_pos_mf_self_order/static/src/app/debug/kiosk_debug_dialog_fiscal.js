/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import {
    AlertDialog,
    ConfirmationDialog,
} from "@web/core/confirmation_dialog/confirmation_dialog";
import { KioskDebugDialog } from "@l10n_ve_pos_self_order/app/debug/kiosk_debug_dialog";

// Órdenes pendientes que se listan en el aviso de bloqueo (igual que la caja).
const MAX_PENDING_SHOWN = 10;

/**
 * Extensión fiscal del panel de Debug del Kiosko (`KioskDebugDialog`, base).
 *
 * Añade las herramientas de la MÁQUINA FISCAL (pareo del puerto Web Serial y
 * comprobación del estado de conexión) sobre el shell genérico de base (que ya
 * trae "Ver órdenes" y los reintentos de la cola de registro).
 *
 * El Kiosko conecta bajo demanda (abre el puerto solo durante cada
 * impresión/pareo y lo libera al terminar, ver `self_order_fiscal.js`), así que
 * el badge de estado NO puede leer un flag "conectado" en memoria — en reposo
 * sería casi siempre falso aunque todo esté bien. Por eso el estado mostrado es
 * el resultado de la ÚLTIMA prueba explícita (pareo/"Comprobar estado").
 */
patch(KioskDebugDialog.prototype, {
    setup() {
        super.setup(...arguments);
        this.state.connected = null;
    },

    get connected() {
        return this.state.connected;
    },

    _describe(res) {
        if (res === true) {
            return _t("Fiscal machine connected.");
        }
        if (res === false) {
            return _t("Could not connect the fiscal machine.");
        }
        return super._describe(res);
    },

    onCheckStatus() {
        this._run(_t("Check connection status"), async () => {
            if (typeof this.selfOrder.checkFiscalPrinterConnection !== "function") {
                return { valid: false, message: _t("Not available") };
            }
            const ok = await this.selfOrder.checkFiscalPrinterConnection();
            this.state.connected = ok;
            return ok;
        });
    },

    onPair() {
        this._run(_t("Pair fiscal machine"), async () => {
            const ok = await this.selfOrder.pairFiscalPrinter();
            this.state.connected = ok;
            return ok;
        });
    },

    _mfAlert(title, body, props = {}) {
        this.dialog.add(AlertDialog, { title, body, ...props });
    },

    /** Confirmación de la Z (irreversible), con el texto de la caja. */
    _confirmReportZ() {
        return new Promise((resolve) => {
            this.dialog.add(
                ConfirmationDialog,
                {
                    title: _t("Confirm Z report"),
                    body: _t(
                        "The Z report will close the current fiscal day. This action is irreversible. Do you want to continue?"
                    ),
                    confirm: () => resolve(true),
                    cancel: () => resolve(false),
                },
                { onClose: () => resolve(false) }
            );
        });
    },

    /**
     * Cerrar sesión e imprimir Z (ticket 16406). Mismo flujo que el botón de la
     * caja (`ClosePosPopup.closeSessionAndPrintZ` de l10n_ve_pos_mf):
     *  1. si hay órdenes de la sesión sin número fiscal, avisa y no sigue;
     *  2. pide confirmación (la Z es irreversible);
     *  3. lee S1 e imprime la Z;
     *  4. sincroniza la Z con Odoo;
     *  5. cierra la sesión con el cierre nativo del Kiosko.
     * Cualquier fallo corta el flujo en ese paso. Antes de empezar, tampoco
     * sigue si hay una factura fiscal imprimiéndose (la Z se metería en medio)
     * o si la sesión ya tiene su Z (otra Z cerraría un día vacío).
     */
    onCloseSessionAndPrintZ() {
        return this._run(_t("Close session and print Z"), async () => {
            if (this.selfOrder.isPrintingKioskFiscalInvoice) {
                return {
                    valid: false,
                    message: _t("A fiscal invoice is being printed. Try again when it finishes."),
                };
            }

            const check = await this.selfOrder.checkKioskCloseSession();
            if (check.report_z) {
                const body = _t(
                    "This session already has its Z report (no. %s). Close it from the backend.",
                    check.report_z
                );
                this._mfAlert(_t("The session cannot be closed"), body);
                return { valid: false, message: body };
            }
            const pending = check.pending_orders;
            if (pending.length) {
                this._alertPendingOrders(pending);
                return {
                    valid: false,
                    message: _t("%s order(s) without a fiscal invoice.", pending.length),
                };
            }

            if (!(await this._confirmReportZ())) {
                return { valid: true, message: _t("Cancelled.") };
            }

            const zResult = await this.selfOrder.printKioskReportZ();
            if (!zResult.success) {
                this._mfAlert(_t("Error printing the Z report"), zResult.error);
                return { valid: false, message: zResult.error };
            }

            const synced = await this.selfOrder.syncKioskReportZ(zResult.value);
            if (!synced.success) {
                const body = _t(
                    "The Z report was printed, but Odoo could not be updated (reason: %s). The session was not closed. Check the sales book and close the session from the backend.",
                    synced.error || _t("unknown error")
                );
                this._mfAlert(_t("Z report printed with a warning"), body);
                return { valid: false, message: body };
            }

            const closed = await this.selfOrder.closeKioskSession();
            if (!closed.success) {
                const body = _t(
                    "The Z report was printed and synced, but the session could not be closed (reason: %s). Close it from the backend.",
                    closed.error || _t("unknown error")
                );
                this._mfAlert(_t("Session not closed"), body);
                return { valid: false, message: body };
            }
            return { valid: true, message: _t("Z report printed and session closed.") };
        });
    },

    /**
     * Aviso de bloqueo con las órdenes pendientes. Las pagadas se resuelven en
     * el panel de Órdenes (el aviso lo abre: `checkKioskCloseSession` ya las
     * cargó aunque no estén entre las últimas); las que quedaron en borrador con
     * un pago no aparecen en el panel y se resuelven desde el backend.
     */
    _alertPendingOrders(pending) {
        const shown = pending
            .slice(0, MAX_PENDING_SHOWN)
            .map((order) => {
                const ref = order.pos_reference || order.name;
                return order.state === "draft"
                    ? _t("%s (unfinished order with a payment: resolve it from the backend)", ref)
                    : ref;
            })
            .join("\n");
        const more = pending.length - MAX_PENDING_SHOWN;
        // Sin concatenar: `_t` es perezoso y se resuelve al mostrarse.
        const orders =
            more > 0 ? _t("%(orders)s\n... and %(more)s more", { orders: shown, more }) : shown;
        const body = _t(
            "There are %(count)s order(s) without a fiscal invoice in this session. Create their invoice or print them from Orders before closing:\n\n%(orders)s",
            { count: pending.length, orders }
        );
        const fromPanel = pending.some((order) => order.state !== "draft");
        this._mfAlert(
            _t("The session cannot be closed"),
            body,
            fromPanel ? { confirmLabel: _t("Open Orders"), confirm: () => this.onOpenOrders() } : {}
        );
    },
});
