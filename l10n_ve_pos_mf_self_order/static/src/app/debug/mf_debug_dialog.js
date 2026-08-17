/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

/**
 * Panel de Debug de la Máquina Fiscal para el Kiosko.
 *
 * Se abre desde un botón flotante visible SOLO en modo debug (`?debug=1`).
 * Centraliza las herramientas de diagnóstico/recuperación de la máquina fiscal
 * (pareo del puerto Web Serial, estado de conexión, reimpresión de la última
 * factura pendiente). Pensado para ir agregando opciones: cada acción es un
 * botón + un método que delega en el servicio `self_order`
 * (l10n_ve_pos_mf_self_order/overrides/self_order_fiscal.js).
 */
export class MfDebugDialog extends Component {
    static components = { Dialog };
    static template = "l10n_ve_pos_mf_self_order.MfDebugDialog";
    static props = { close: Function };

    setup() {
        this.selfOrder = useService("self_order");
        this.state = useState({ busy: false, message: "" });
    }

    get connected() {
        return (
            typeof this.selfOrder.useFiscalMachine === "function" &&
            this.selfOrder.useFiscalMachine()
        );
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
        if (res && res.valid) {
            const ref = res.order && (res.order.pos_reference || res.order.uuid);
            return ref ? _t("OK — orden %s.", ref) : _t("OK.");
        }
        if (res && res.message) {
            return _t("Falló: %s", res.message);
        }
        return _t("Listo.");
    }

    onCheckStatus() {
        this.state.message = this.connected
            ? _t("Máquina fiscal: CONECTADA.")
            : _t("Máquina fiscal: DESCONECTADA.");
    }

    onPair() {
        this._run(_t("Parear máquina fiscal"), () => this.selfOrder.pairFiscalPrinter());
    }

    onReprint() {
        this._run(_t("Reimprimir última factura"), () =>
            this.selfOrder.reprintLastKioskFiscalInvoice()
        );
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
            await this.selfOrder.retryFailedKioskRegistrations();
            const left = this.failedCount;
            return {
                valid: left === 0,
                message: left
                    ? _t("Quedan %s orden(es) fallida(s) — revisar la causa.", left)
                    : _t("Sin órdenes fallidas."),
            };
        });
    }
}
