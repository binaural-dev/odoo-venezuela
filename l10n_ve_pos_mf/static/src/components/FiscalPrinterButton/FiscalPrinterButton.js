/** @odoo-module */

import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
import { TfhkaDriver } from "@l10n_ve_mf_base/drivers/TfhkaDriver";

/**
 * Botón de conexión con la máquina fiscal (top-right del navbar POS).
 *
 * Estados: disconnected | connecting | connected | error
 *
 * - Al montar: intenta reconexión silenciosa (autoConnect con puerto
 *   previamente autorizado por el usuario).
 * - Click con máquina desconectada: solicita permiso Web Serial (prompt
 *   de selección de puerto del navegador) y conecta.
 * - Click con máquina conectada: desconecta.
 *
 * El driver conectado se expone en window.fiscalPrinter para que el resto
 * del POS (PosStore.pushToMF, reimpresión, reportes) lo utilice.
 */
export class FiscalPrinterButton extends Component {
    static template = "l10n_ve_pos_mf.FiscalPrinterButton";
    static props = {};

    setup() {
        this.pos = usePos();
        this.state = useState({ status: "disconnected" });
        this._onSerialConnect = this._onSerialConnect.bind(this);
        this._onSerialDisconnect = this._onSerialDisconnect.bind(this);
        this._onFiscalStatus = this._onFiscalStatus.bind(this);
        onMounted(() => {
            this._autoConnect();
            // El hand-off (PosStore.withFiscalPrinterReleased) reconecta/suelta
            // la MF sin pasar por este componente; escuchamos su estado para no
            // quedar en verde tras un reclaim fallido.
            window.addEventListener("mf-fiscal-status", this._onFiscalStatus);
            // Recuperación mid-sesión: la máquina fiscal puede re-enumerar en
            // el bus USB (glitch de energía del hub, sobre todo en PCs de
            // gama baja) sin que se recargue la pestaña. Sin esto, la MF
            // quedaba "desconectada" hasta que el cajero pulsaba el botón.
            if ("serial" in navigator) {
                navigator.serial.addEventListener("connect", this._onSerialConnect);
                navigator.serial.addEventListener("disconnect", this._onSerialDisconnect);
            }
        });
        onWillUnmount(() => {
            window.removeEventListener("mf-fiscal-status", this._onFiscalStatus);
            if ("serial" in navigator) {
                navigator.serial.removeEventListener("connect", this._onSerialConnect);
                navigator.serial.removeEventListener("disconnect", this._onSerialDisconnect);
            }
        });
    }

    /**
     * Estado de la MF notificado por el hand-off (PosStore._broadcastFiscalStatus).
     * No pisa una reconexión en curso del propio botón.
     */
    _onFiscalStatus(ev) {
        if (this._reconnecting) {
            return;
        }
        this._setStatus(ev?.detail?.connected ? "connected" : "disconnected");
    }

    _fp() {
        return this.fiscalPrinter || window.fiscalPrinter || null;
    }

    /**
     * Un puerto serial autorizado reapareció (re-enumeración USB). Intenta
     * reconectar en silencio; connect() → autoConnect() filtra por identidad
     * (VID/PID), así que solo tendrá éxito si es realmente la máquina fiscal.
     */
    async _onSerialConnect() {
        const fp = this._fp();
        // No pisar una conexión en curso: el `connect` inicial del bus puede
        // llegar mientras el _autoConnect del montaje aún conecta (isConnected
        // todavía false), y dos connect() concurrentes sobre el mismo puerto
        // dejan el estado inconsistente.
        if (!fp || fp.isConnected || this._reconnecting || this.state.status === "connecting") {
            return;
        }
        this._reconnecting = true;
        this._setStatus("connecting");
        try {
            // Cerrar cualquier handle viejo ANTES de reconectar. Es lo que
            // hace el "apagar/prender" manual del botón (el único camino que
            // reconectaba limpio): tras una re-enumeración USB el puerto
            // anterior queda medio-abierto y reabrir sin cerrar deja los
            // streams en null → getStatus()/write() reventaban.
            try {
                await fp.disconnect();
            } catch (e) {
                // El handle viejo pudo perderse físicamente; da igual, vamos
                // a reconectar con un puerto fresco de todas formas.
            }
            const connected = await fp.connect();
            this._setStatus(connected ? "connected" : "disconnected");
        } catch (error) {
            console.warn("FiscalPrinter:: reconexión automática tras re-enumeración falló", error);
            this._setStatus("disconnected");
        } finally {
            this._reconnecting = false;
        }
    }

    /**
     * Un puerto serial desapareció. Si es el nuestro, refleja el estado como
     * desconectado (el listener de connect lo recuperará si vuelve).
     */
    _onSerialDisconnect(event) {
        const fp = this._fp();
        const port = fp && fp.connection ? fp.connection.port : null;
        if (!fp || !port || (event && event.target && event.target !== port)) {
            return;
        }
        fp.isConnected = false;
        if (fp.connection) {
            fp.connection.isConnected = false;
            fp.connection.port = null;
        }
        this._setStatus("disconnected");
    }

    get statusTitle() {
        return {
            disconnected: "Máquina Fiscal: Desconectada",
            connecting: "Máquina Fiscal: Conectando...",
            connected: "Máquina Fiscal: Conectada",
            error: "Máquina Fiscal: Error",
        }[this.state.status];
    }

    _setStatus(status) {
        this.state.status = status;
    }

    async _autoConnect() {
        if (!("serial" in navigator)) {
            this._setStatus("error");
            console.error("FiscalPrinter:: Web Serial API no soportada en este navegador");
            return;
        }

        try {
            if (!window.fiscalPrinter) {
                window.fiscalPrinter = new TfhkaDriver();
            }
            this.fiscalPrinter = window.fiscalPrinter;

            if (this.fiscalPrinter.isConnected) {
                this._setStatus("connected");
                return;
            }

            this._setStatus("connecting");
            const connected = await this.fiscalPrinter.connect();
            this._setStatus(connected ? "connected" : "disconnected");
        } catch (error) {
            console.error("FiscalPrinter:: Error en inicialización", error);
            this._setStatus("error");
        }
    }

    async onClick() {
        if (this.state.status === "connected") {
            await this._disconnect();
        } else {
            await this._connect();
        }
    }

    async _connect() {
        try {
            if (!window.fiscalPrinter) {
                window.fiscalPrinter = new TfhkaDriver();
            }
            this.fiscalPrinter = window.fiscalPrinter;

            this._setStatus("connecting");

            // Solicita permiso al usuario para seleccionar el puerto serial
            const connected = await this.fiscalPrinter.connect({ requestPermission: true });

            if (connected) {
                const status = await this.fiscalPrinter.getStatus();
                if (status) {
                    this.fiscalPrinter.isConnected = true;
                    this._setStatus("connected");
                } else {
                    this._setStatus("error");
                    console.error("FiscalPrinter:: La impresora no responde");
                }
            } else {
                this._setStatus("disconnected");
            }
        } catch (error) {
            console.error("FiscalPrinter:: Error al conectar", error);
            this._setStatus("error");
        }
    }

    async _disconnect() {
        try {
            if (this.fiscalPrinter) {
                await this.fiscalPrinter.disconnect();
            }
            this._setStatus("disconnected");
        } catch (error) {
            console.error("FiscalPrinter:: Error al desconectar", error);
        }
    }
}
