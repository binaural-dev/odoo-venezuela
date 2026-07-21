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
     * Inicializa el driver de la máquina fiscal
     * @private
     */
    async _initFiscalPrinter() {
        try {
            this.fiscalPrinter = new TfhkaDriver();
            
            // Intentar reconexión automática
            this._updateFiscalPrinterButtonStatus("connecting");
            const connected = await this.fiscalPrinter.connect();
            
            if (connected) {
                this._updateFiscalPrinterButtonStatus("connected");
                window.fiscalPrinter = this.fiscalPrinter; // Exponer globalmente
            } else {
                this._updateFiscalPrinterButtonStatus("disconnected");
            }
        } catch (error) {
            console.error("FiscalPrinter:: Error en inicialización", error);
            this._updateFiscalPrinterButtonStatus("error");
        }
    },

    /**
     * Conecta manualmente con la máquina fiscal
     * @private
     */
    async _connectFiscalPrinter() {
        try {
            if (!this.fiscalPrinter) {
                this.fiscalPrinter = new TfhkaDriver();
            }

            this._updateFiscalPrinterButtonStatus("connecting");
            
            // Esto solicitará permiso al usuario para seleccionar el puerto
            const connected = await this.fiscalPrinter.connect({ requestPermission: true });
            
            if (connected) {
                // Verificar que la impresora responda
                const status = await this.fiscalPrinter.getStatus();
                if (status) {
                    this.fiscalPrinter.isConnected = true;
                    this._updateFiscalPrinterButtonStatus("connected");
                    window.fiscalPrinter = this.fiscalPrinter;
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
     * Desconecta la máquina fiscal
     * @private
     */
    async _disconnectFiscalPrinter() {
        try {
            if (this.fiscalPrinter) {
                await this.fiscalPrinter.disconnect();
                window.fiscalPrinter = null;
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
