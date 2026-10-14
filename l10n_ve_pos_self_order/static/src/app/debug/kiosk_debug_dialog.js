/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { KioskOrdersDialog } from "@l10n_ve_pos_self_order/app/debug/kiosk_orders_dialog";

/**
 * Panel de Debug del Kiosko.
 *
 * Se abre desde un botón flotante visible SOLO en modo debug (`?debug=1`).
 * Centraliza las herramientas de diagnóstico/recuperación del Kiosko que NO
 * dependen de la máquina fiscal: abrir el panel de órdenes (crear factura de las
 * pendientes) y reintentar el REGISTRO de órdenes en la cola durable
 * (`kiosk_sync_queue.js`, persistencia de base).
 *
 * `l10n_ve_pos_mf_self_order` extiende este mismo componente y plantilla (patch
 * + t-inherit) para añadir las herramientas de la máquina fiscal (pareo del
 * puerto Web Serial, comprobar estado de conexión).
 */
export class KioskDebugDialog extends Component {
    static components = { Dialog };
    static template = "l10n_ve_pos_self_order.KioskDebugDialog";
    static props = { close: Function };

    setup() {
        this.selfOrder = useService("self_order");
        this.dialog = useService("dialog");
        this.state = useState({ busy: false, message: "" });
    }

    get dialogTitle() {
        return _t("Kiosk Debug");
    }

    async _run(label, fn) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.message = _t("Running: %s…", label);
        try {
            const res = await fn();
            this.state.message = this._describe(res);
        } catch (error) {
            console.error("[Kiosk][debug]", error);
            this.state.message = _t("Error: %s", String((error && error.message) || error));
        } finally {
            this.state.busy = false;
        }
    }

    _describe(res) {
        // Chequear `message` ANTES que `valid`: algunas acciones (reintentar
        // pendientes/fallidas) devuelven valid=true con un resumen propio
        // ("No pending orders.") que el genérico "OK." de abajo pisaría.
        if (res && res.message) {
            return res.valid ? res.message : _t("Failed: %s", res.message);
        }
        if (res && res.valid) {
            const ref = res.order && (res.order.pos_reference || res.order.uuid);
            return ref ? _t("OK — order %s.", ref) : _t("OK.");
        }
        return _t("Done.");
    }

    onOpenOrders() {
        this.dialog.add(KioskOrdersDialog, {});
    }

    get pendingCount() {
        return typeof this.selfOrder.kioskPendingCount === "number"
            ? this.selfOrder.kioskPendingCount
            : 0;
    }

    get failedCount() {
        return typeof this.selfOrder.kioskFailedCount === "number"
            ? this.selfOrder.kioskFailedCount
            : 0;
    }

    onFlushQueue() {
        this._run(_t("Retry pending registration"), async () => {
            if (typeof this.selfOrder.flushKioskRegistrations !== "function") {
                return { valid: false, message: _t("Queue not available") };
            }
            await this.selfOrder.flushKioskRegistrations();
            const left = this.pendingCount;
            return {
                valid: left === 0,
                message: left
                    ? _t("%s order(s) still pending.", left)
                    : _t("No pending orders."),
            };
        });
    }

    onRetryFailed() {
        this._run(_t("Retry FAILED orders"), async () => {
            if (typeof this.selfOrder.retryFailedKioskRegistrations !== "function") {
                return { valid: false, message: _t("Not available") };
            }
            const result = await this.selfOrder.retryFailedKioskRegistrations();
            const remaining = (result && result.remaining) || [];
            if (!remaining.length) {
                return { valid: true, message: _t("No failed orders.") };
            }
            // Mostrar el motivo real guardado por flushKioskRegistrations
            // (`errorMessage`) en vez de un genérico "revisar la causa".
            const reasons = remaining
                .map((entry) => {
                    const ref = (entry.uuid || "").slice(0, 8);
                    const reason = entry.errorMessage || _t("(no detail)");
                    return `${ref}: ${reason}`;
                })
                .join(" | ");
            return {
                valid: false,
                message: _t("%s failed order(s) remaining — %s", remaining.length, reasons),
            };
        });
    }
}
