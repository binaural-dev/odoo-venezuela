/** @odoo-module */

import { Component, onMounted, useState } from "@odoo/owl";
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
        onMounted(() => this._autoConnect());
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
