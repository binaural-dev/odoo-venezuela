/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, xml, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { getBackendFiscalPrinter } from "./mf_webserial_service";

/**
 * Systray item de Máquina Fiscal (Web Serial) para el backend.
 *
 * - Muestra si el dispositivo está pareado/listo (NO si el puerto está
 *   físicamente abierto en este instante): bajo el modelo de conexión bajo
 *   demanda, el puerto solo se abre durante una operación puntual
 *   (withConnection) y se libera de inmediato, para no monopolizar el
 *   puerto COM mientras la pestaña de backoffice esté simplemente abierta
 *   sin imprimir nada (eso bloqueaba al POS u otra pestaña).
 * - Click: parea (prompt de puerto serial) si hace falta, o hace una prueba
 *   puntual de comunicación (ENQ) si ya está pareada.
 *
 * Paridad visual/funcional con el botón de máquina fiscal del POS
 * (l10n_ve_pos_mf/static/src/overrides/pos_app.js), que sigue el mismo
 * modelo de "pareado" vs "puerto abierto ahora mismo".
 */
export class MfConnectionSystray extends Component {
    static props = {};
    static template = xml`
        <div class="o_mf_systray d-flex align-items-center px-2"
             role="button"
             t-att-title="statusTitle"
             t-on-click="onClick">
            <i t-att-class="iconClass"/>
        </div>`;

    setup() {
        this.notification = useService("notification");
        this.state = useState({
            status: "disconnected", // disconnected | connecting | connected(paired) | error
        });
        this._pollId = null;

        onMounted(() => {
            this._refreshPairedStatus();
            // Sincroniza el badge si el dispositivo se parea desde otra
            // pestaña — nunca abre el puerto, solo consulta getPorts().
            this._pollId = setInterval(() => this._refreshPairedStatus(), 10000);
        });
        onWillUnmount(() => {
            if (this._pollId) {
                clearInterval(this._pollId);
                this._pollId = null;
            }
        });
    }

    get statusTitle() {
        const titles = {
            disconnected: _t("Máquina Fiscal: No pareada (click para parear)"),
            connecting: _t("Máquina Fiscal: Conectando..."),
            connected: _t("Máquina Fiscal: Pareada (click para probar comunicación)"),
            error: _t("Máquina Fiscal: Error (click para reintentar)"),
        };
        return titles[this.state.status] || titles.disconnected;
    }

    get iconClass() {
        const colors = {
            disconnected: "text-muted",
            connecting: "text-warning",
            connected: "text-success",
            error: "text-danger",
        };
        const spin = this.state.status === "connecting" ? " fa-spin" : "";
        const icon = this.state.status === "connecting" ? "fa-circle-o-notch" : "fa-print";
        return `fa ${icon}${spin} ${colors[this.state.status] || "text-muted"}`;
    }

    /**
     * Consulta si el dispositivo ya está autorizado en este navegador SIN
     * abrir el puerto (`getPorts()` solo lista pareos ya concedidos).
     */
    async _refreshPairedStatus() {
        if (this.state.status === "connecting" || !("serial" in navigator)) {
            return;
        }
        try {
            const ports = await navigator.serial.getPorts();
            const driver = getBackendFiscalPrinter();
            driver.isPaired = ports.length > 0;
            this.state.status = driver.isPaired ? "connected" : "disconnected";
        } catch (error) {
            console.warn("MfSystray:: No se pudo verificar el pareo", error);
        }
    }

    async onClick() {
        if (this.state.status === "connecting") {
            return;
        }

        if (!("serial" in navigator)) {
            this.notification.add(
                _t("Este navegador no soporta Web Serial API. Usa Chrome/Edge en contexto seguro (https o localhost)."),
                { title: _t("Máquina Fiscal"), type: "danger", sticky: true }
            );
            return;
        }

        const driver = getBackendFiscalPrinter();

        if (this.state.status === "connected") {
            // Web Serial no permite revocar un pareo desde JS (solo el
            // usuario puede hacerlo desde la configuración del navegador).
            // El puerto no se mantiene abierto fuera de una operación real,
            // así que aquí solo hacemos una prueba puntual de comunicación.
            try {
                this.state.status = "connecting";
                const status = await driver.withConnection(() => driver.getStatus());
                this.state.status = "connected";
                this.notification.add(
                    status
                        ? _t("La máquina fiscal responde correctamente")
                        : _t("La máquina fiscal no respondió"),
                    { title: _t("Máquina Fiscal"), type: status ? "success" : "warning" }
                );
            } catch (error) {
                console.error("MfSystray:: Error al probar la máquina fiscal", error);
                this.state.status = "connected";
                this.notification.add(
                    error?.message || _t("No se pudo comunicar con la máquina fiscal"),
                    { title: _t("Máquina Fiscal"), type: "warning" }
                );
            }
            return;
        }

        // Parear (gesto de usuario, prompt de selección de puerto) y soltar
        // de inmediato — el ciclo real de conexión lo abre withConnection()
        // bajo demanda en cada impresión/operación.
        try {
            this.state.status = "connecting";
            const connected = await driver.connect({ requestPermission: true });
            if (connected) {
                await driver.disconnect();
                this.state.status = "connected";
                this.notification.add(_t("Máquina fiscal pareada correctamente"), {
                    title: _t("Máquina Fiscal"),
                    type: "success",
                });
            } else {
                this.state.status = "disconnected";
                this.notification.add(
                    _t("No se pudo conectar con la máquina fiscal. Verifica el cable y el puerto."),
                    { title: _t("Máquina Fiscal"), type: "warning" }
                );
            }
        } catch (error) {
            console.error("MfSystray:: Error al parear", error);
            this.state.status = "error";
        }
    }
}

export const mfConnectionSystrayItem = {
    Component: MfConnectionSystray,
};

registry.category("systray").add("l10n_ve_iot_mf.MfConnectionSystray", mfConnectionSystrayItem, {
    sequence: 26,
});
