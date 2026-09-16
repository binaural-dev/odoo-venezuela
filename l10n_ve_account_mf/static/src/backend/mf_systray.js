/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, xml, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import { getBackendFiscalPrinter } from "./mf_webserial_service";

/**
 * Systray item de Máquina Fiscal (Web Serial) para el backend.
 *
 * - Muestra el estado de conexión (desconectada / conectando / conectada / error).
 * - Click: conecta manualmente (prompt de puerto serial) o desconecta si ya está conectada.
 *
 * Paridad visual/funcional con el botón de máquina fiscal del POS
 * (l10n_ve_pos_mf/static/src/overrides/pos_app.js).
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
            status: "disconnected", // disconnected | connecting | connected | error
        });
        this._pollId = null;

        onMounted(() => {
            this._autoConnect();
            // Mantener el badge sincronizado si otro componente conecta/desconecta
            this._pollId = setInterval(() => this._refreshFromDriver(), 5000);
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
            disconnected: _t("Máquina Fiscal: Desconectada (click para conectar)"),
            connecting: _t("Máquina Fiscal: Conectando..."),
            connected: _t("Máquina Fiscal: Conectada (click para desconectar)"),
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

    _refreshFromDriver() {
        if (this.state.status === "connecting") {
            return;
        }
        const driver = getBackendFiscalPrinter();
        const connected = Boolean(driver.isConnected);
        if (connected && this.state.status !== "connected") {
            this.state.status = "connected";
        } else if (!connected && this.state.status === "connected") {
            this.state.status = "disconnected";
        }
    }

    /**
     * Reconexión automática silenciosa al cargar el backend
     * (solo si el puerto ya fue autorizado previamente).
     */
    async _autoConnect() {
        if (!("serial" in navigator)) {
            return;
        }
        const driver = getBackendFiscalPrinter();
        if (driver.isConnected) {
            this.state.status = "connected";
            return;
        }
        try {
            this.state.status = "connecting";
            const connected = await driver.connection.autoConnect();
            if (connected) {
                const status = await driver.getStatus();
                if (status) {
                    driver.isConnected = true;
                    this.state.status = "connected";
                    return;
                }
            }
            this.state.status = "disconnected";
        } catch (error) {
            console.warn("MfSystray:: Falló la reconexión automática", error);
            this.state.status = "disconnected";
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
            try {
                await driver.disconnect();
                this.state.status = "disconnected";
                this.notification.add(_t("Máquina fiscal desconectada"), {
                    title: _t("Máquina Fiscal"),
                    type: "info",
                });
            } catch (error) {
                console.error("MfSystray:: Error al desconectar", error);
                this.state.status = "error";
            }
            return;
        }

        // Conectar manualmente (prompt de selección de puerto).
        // Fix v17→v19: el click manual debe pasar requestPermission para
        // poder autorizar el puerto por primera vez desde el backend.
        try {
            this.state.status = "connecting";
            let connected = await driver.connect();
            if (!connected) {
                connected = await driver.connect({ requestPermission: true });
            }
            if (connected) {
                this.state.status = "connected";
                this.notification.add(_t("Máquina fiscal conectada"), {
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
            console.error("MfSystray:: Error al conectar", error);
            this.state.status = "error";
        }
    }
}

export const mfConnectionSystrayItem = {
    Component: MfConnectionSystray,
};

registry.category("systray").add("l10n_ve_account_mf.MfConnectionSystray", mfConnectionSystrayItem, {
    sequence: 26,
});
