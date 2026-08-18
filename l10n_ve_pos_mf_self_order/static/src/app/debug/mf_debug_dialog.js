/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { KioskFiscalOrdersDialog } from "@l10n_ve_pos_mf_self_order/app/debug/kiosk_fiscal_orders_dialog";

/**
 * Panel de Debug de la Máquina Fiscal para el Kiosko.
 *
 * Se abre desde un botón flotante visible SOLO en modo debug (`?debug=1`).
 * Centraliza las herramientas de diagnóstico/recuperación de la máquina fiscal
 * (pareo del puerto Web Serial, estado de conexión, reimpresión de la última
 * factura pendiente). Pensado para ir agregando opciones: cada acción es un
 * botón + un método que delega en el servicio `self_order`
 * (l10n_ve_pos_mf_self_order/overrides/self_order_fiscal.js).
 *
 * El Kiosko conecta bajo demanda (abre el puerto solo durante cada
 * impresión/pareo y lo libera al terminar, ver `self_order_fiscal.js`), así
 * que el badge de estado NO puede leer un flag "conectado" en memoria — en
 * reposo sería casi siempre falso aunque todo esté bien. Por eso el estado
 * mostrado aquí es el resultado de la ÚLTIMA prueba explícita
 * (pareo/"Comprobar estado"), no una lectura reactiva continua.
 */
export class MfDebugDialog extends Component {
    static components = { Dialog };
    static template = "l10n_ve_pos_mf_self_order.MfDebugDialog";
    static props = { close: Function };

    setup() {
        this.selfOrder = useService("self_order");
        this.dialog = useService("dialog");
        this.state = useState({ busy: false, message: "", connected: null });
    }

    get connected() {
        return this.state.connected;
    }

    async _run(label, fn) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.message = _t("Ejecutando: %s…", label);
        try {
            const res = await fn();
            this.state.message = this._describe(res);
        } catch (error) {
            console.error("[MF Kiosk][debug]", error);
            this.state.message = _t("Error: %s", String((error && error.message) || error));
        } finally {
            this.state.busy = false;
        }
    }

    _describe(res) {
        if (res === true) {
            return _t("Máquina fiscal conectada.");
        }
        if (res === false) {
            return _t("No se pudo conectar la máquina fiscal.");
        }
        // Chequear `message` ANTES que `valid`: algunas acciones (reintentar
        // pendientes/fallidas) devuelven valid=true con un resumen propio
        // ("Sin órdenes pendientes.") que el genérico "OK." de abajo pisaría.
        if (res && res.message) {
            return res.valid ? res.message : _t("Falló: %s", res.message);
        }
        if (res && res.valid) {
            const ref = res.order && (res.order.pos_reference || res.order.uuid);
            return ref ? _t("OK — orden %s.", ref) : _t("OK.");
        }
        return _t("Listo.");
    }

    onCheckStatus() {
        this._run(_t("Comprobar estado de conexión"), async () => {
            if (typeof this.selfOrder.checkFiscalPrinterConnection !== "function") {
                return { valid: false, message: _t("No disponible") };
            }
            const ok = await this.selfOrder.checkFiscalPrinterConnection();
            this.state.connected = ok;
            return ok;
        });
    }

    onPair() {
        this._run(_t("Parear máquina fiscal"), async () => {
            const ok = await this.selfOrder.pairFiscalPrinter();
            this.state.connected = ok;
            return ok;
        });
    }

    onOpenOrders() {
        this.dialog.add(KioskFiscalOrdersDialog, {});
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
        this._run(_t("Reintentar registro pendiente"), async () => {
            if (typeof this.selfOrder.flushKioskRegistrations !== "function") {
                return { valid: false, message: _t("Cola no disponible") };
            }
            await this.selfOrder.flushKioskRegistrations();
            const left = this.pendingCount;
            return {
                valid: left === 0,
                message: left
                    ? _t("Quedan %s orden(es) pendiente(s).", left)
                    : _t("Sin órdenes pendientes."),
            };
        });
    }

    onRetryFailed() {
        this._run(_t("Reintentar órdenes FALLIDAS"), async () => {
            if (typeof this.selfOrder.retryFailedKioskRegistrations !== "function") {
                return { valid: false, message: _t("No disponible") };
            }
            const result = await this.selfOrder.retryFailedKioskRegistrations();
            const remaining = (result && result.remaining) || [];
            if (!remaining.length) {
                return { valid: true, message: _t("Sin órdenes fallidas.") };
            }
            // Mostrar el motivo real guardado por flushKioskRegistrations
            // (`errorMessage`) en vez de un genérico "revisar la causa".
            const reasons = remaining
                .map((entry) => {
                    const ref = (entry.uuid || "").slice(0, 8);
                    const reason = entry.errorMessage || _t("(sin detalle)");
                    return `${ref}: ${reason}`;
                })
                .join(" | ");
            return {
                valid: false,
                message: _t("Quedan %s orden(es) fallida(s) — %s", remaining.length, reasons),
            };
        });
    }
}
