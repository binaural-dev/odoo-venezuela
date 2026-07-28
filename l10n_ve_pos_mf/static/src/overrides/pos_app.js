/** @odoo-module */

import { Chrome } from "@point_of_sale/app/pos_app";
import { patch } from "@web/core/utils/patch";
import { onMounted, onWillUnmount } from "@odoo/owl";
import { TfhkaDriver } from "@l10n_ve_mf_base/drivers/TfhkaDriver";
import { useService } from "@web/core/utils/hooks";
import { LocalOrderBuffer } from "../utils/LocalOrderBuffer";

/**
 * Override del componente principal del POS para inicializar el driver de la máquina fiscal
 */
patch(Chrome.prototype, {
    
    setup() {
        super.setup(...arguments);
        this.fiscalPrinter = null;
        this.fiscalPrinterStatus = "disconnected";
        this.autoSyncIntervalId = null;
        this.isFlushingPendingOrders = false;
        this.orm = useService("orm");
        onMounted(() => this._onMountedFiscalPrinter());
        onWillUnmount(() => this._clearAutoSyncInterval());
    },

    async _onMountedFiscalPrinter() {
        this._createFiscalPrinterButton();
        await this._initFiscalPrinter();
        
        // Intentar sincronizar pedidos offline pendientes
        await this._flushPendingOrders();
        this._setupAutoSync();
    },

    _getAutoSyncConfig() {
        const posConfig = this.env.services.pos?.config || {};
        const enableAutoSync = posConfig.enable_auto_sync !== false;
        const configuredInterval = Number(posConfig.auto_sync_interval || 60);
        const intervalSeconds = Number.isFinite(configuredInterval)
            ? Math.max(10, configuredInterval)
            : 60;

        return {
            enableAutoSync,
            intervalSeconds,
        };
    },

    _setupAutoSync() {
        const { enableAutoSync, intervalSeconds } = this._getAutoSyncConfig();
        this._clearAutoSyncInterval();

        if (!enableAutoSync) {
            return;
        }

        this.autoSyncIntervalId = setInterval(async () => {
            if (!navigator.onLine || !LocalOrderBuffer.hasPending()) {
                return;
            }
            await this._flushPendingOrders();
        }, intervalSeconds * 1000);

    },

    _clearAutoSyncInterval() {
        if (this.autoSyncIntervalId) {
            clearInterval(this.autoSyncIntervalId);
            this.autoSyncIntervalId = null;
        }
    },

    _createFiscalPrinterButton() {
        this.fiscalPrinterBtn = $("<button class='fiscal-printer-action fa fa-print' title='Máquina Fiscal'/>");
        $(".status-buttons").prepend(this.fiscalPrinterBtn);
        this.fiscalPrinterBtn.on('click', this._handleFiscalPrinterClick.bind(this));
        this._updateFiscalPrinterButtonStatus("disconnected");
    },

    /**
     * Actualiza el estilo del botón según el estado de conexión
     * @param {string} status - disconnected, connecting, connected, error
     * @private
     */
    _updateFiscalPrinterButtonStatus(status) {
        this.fiscalPrinterStatus = status;
        this.fiscalPrinterBtn.removeClass("fiscal-printer-disconnected fiscal-printer-connecting fiscal-printer-connected fiscal-printer-error");
        this.fiscalPrinterBtn.addClass(`fiscal-printer-${status}`);
        
        const statusText = {
            disconnected: "Máquina Fiscal: Desconectada",
            connecting: "Máquina Fiscal: Conectando...",
            connected: "Máquina Fiscal: Conectada",
            error: "Máquina Fiscal: Error"
        };
        this.fiscalPrinterBtn.attr('title', statusText[status]);
    },

    /**
     * Manejador del click en el botón de máquina fiscal
     * @private
     */
    async _handleFiscalPrinterClick() {
        if (this.fiscalPrinterStatus === "connected") {
            // Si está conectada, desconectar
            await this._disconnectFiscalPrinter();
        } else {
            // Si no está conectada, intentar conectar
            await this._connectFiscalPrinter();
        }
    },

    /**
     * Inicializa el driver de la máquina fiscal. Bajo el modelo de conexión
     * "bajo demanda" (ver TfhkaDriver.withConnection), el puerto ya NO se
     * abre ni se mantiene abierto al montar el POS — cada impresión abre y
     * cierra su propio ciclo. Aquí solo se verifica si el dispositivo ya
     * está autorizado/pareado (sin abrir el puerto), para mostrar un
     * indicador de "listo" al cajero.
     * @private
     */
    async _initFiscalPrinter() {
        try {
            this.fiscalPrinter = new TfhkaDriver();
            window.fiscalPrinter = this.fiscalPrinter; // Exponer globalmente siempre: withConnection() abre el puerto bajo demanda cuando haga falta

            const paired = await this._isFiscalPrinterPaired();
            this.fiscalPrinter.isPaired = paired;
            this._updateFiscalPrinterButtonStatus(paired ? "connected" : "disconnected");
        } catch (error) {
            console.error("FiscalPrinter:: Error en inicialización", error);
            this._updateFiscalPrinterButtonStatus("error");
        }
    },

    /**
     * Indica si ya hay un dispositivo serial autorizado por el usuario en
     * este navegador, SIN abrir el puerto (`getPorts()` solo lista pareos
     * ya concedidos). Esto es lo que alimenta el indicador de "listo".
     * @private
     * @returns {Promise<boolean>}
     */
    async _isFiscalPrinterPaired() {
        try {
            const ports = await navigator.serial.getPorts();
            return ports.length > 0;
        } catch (error) {
            console.error("FiscalPrinter:: Error verificando pareo", error);
            return false;
        }
    },

    /**
     * Autoriza el dispositivo (requiere gesto del usuario la primera vez) y
     * hace una verificación puntual de que responde — luego libera el
     * puerto de inmediato, no se queda conectado.
     * @private
     */
    async _connectFiscalPrinter() {
        try {
            if (!this.fiscalPrinter) {
                this.fiscalPrinter = new TfhkaDriver();
                window.fiscalPrinter = this.fiscalPrinter;
            }

            this._updateFiscalPrinterButtonStatus("connecting");

            // Esto solicitará permiso al usuario para seleccionar el puerto
            // (solo la primera vez; pareos previos se detectan sin gesto)
            const connected = await this.fiscalPrinter.connect({ requestPermission: true });

            if (connected) {
                // Verificar que la impresora responda, y liberar el puerto
                // de inmediato: la conexión bajo demanda no se queda abierta
                // fuera de una impresión real.
                const status = await this.fiscalPrinter.getStatus();
                await this.fiscalPrinter.disconnect();

                if (status) {
                    this._updateFiscalPrinterButtonStatus("connected");
                } else {
                    this._updateFiscalPrinterButtonStatus("error");
                    console.error("FiscalPrinter:: La impresora no responde");
                }
            } else {
                this._updateFiscalPrinterButtonStatus("disconnected");
            }
        } catch (error) {
            console.error("FiscalPrinter:: Error al conectar", error);
            this._updateFiscalPrinterButtonStatus("error");
        }
    },

    /**
     * Web Serial no permite revocar un pareo desde JS (solo el usuario puede
     * hacerlo desde la configuración del navegador) — esto solo limpia el
     * indicador visual de "listo" en esta sesión del POS, no revoca el
     * permiso real. El puerto ya no se mantiene abierto de todas formas
     * (conexión bajo demanda), así que no hay nada que "desconectar" a
     * nivel de hardware en este punto.
     * @private
     */
    async _disconnectFiscalPrinter() {
        try {
            if (this.fiscalPrinter) {
                await this.fiscalPrinter.disconnect();
            }
            this._updateFiscalPrinterButtonStatus("disconnected");
        } catch (error) {
            console.error("FiscalPrinter:: Error al desconectar", error);
        }
    },

    /**
     * Intenta sincronizar pedidos pendientes del buffer offline
     */
    async _flushPendingOrders() {
        if (this.isFlushingPendingOrders) {
            return;
        }

        const buffer = LocalOrderBuffer.getAll();
        
        if (buffer.length === 0) return;

        this.isFlushingPendingOrders = true;
        
        try {
            for (let i = buffer.length - 1; i >= 0; i--) {
                const entry = buffer[i];
                
                try {
                    await this.orm.call("pos.order", "create_from_ui", [[{
                        'data': entry.orderData
                    }]]);
                    
                    LocalOrderBuffer.remove(i);
                    
                } catch (error) {
                    const newRetries = (entry.retries || 0) + 1;
                    LocalOrderBuffer.update(i, { retries: newRetries });
                    console.warn(`FiscalPrinter:: Pedido offline #${i} fallo (intento ${newRetries}):`, error.message);
                    
                    if (newRetries >= 5) {
                        LocalOrderBuffer.remove(i);
                        console.error(`FiscalPrinter:: Pedido offline #${i} abandonado`);
                    }
                }
            }

            LocalOrderBuffer.count();
        } finally {
            this.isFlushingPendingOrders = false;
        }
    },
});
