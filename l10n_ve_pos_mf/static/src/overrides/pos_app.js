/** @odoo-module */

import { Chrome } from "@point_of_sale/app/pos_app";
import { patch } from "@web/core/utils/patch";
import { onMounted } from "@odoo/owl";
import { TfhkaDriver } from "../drivers/TfhkaDriver";
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
        this.orm = useService("orm");
        onMounted(this._onMountedFiscalPrinter);
    },

    async _onMountedFiscalPrinter() {
        this._createFiscalPrinterButton();
        await this._initFiscalPrinter();
        
        // Intentar sincronizar pedidos offline pendientes
        await this._flushPendingOrders();
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
                console.log("FiscalPrinter:: Conexión automática exitosa");
            } else {
                this._updateFiscalPrinterButtonStatus("disconnected");
                console.log("FiscalPrinter:: No se pudo conectar automáticamente");
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
            const connected = await this.fiscalPrinter.connection.requestPort();
            
            if (connected) {
                // Verificar que la impresora responda
                const status = await this.fiscalPrinter.getStatus();
                if (status) {
                    this.fiscalPrinter.isConnected = true;
                    this._updateFiscalPrinterButtonStatus("connected");
                    window.fiscalPrinter = this.fiscalPrinter;
                    console.log("FiscalPrinter:: Conexión manual exitosa", status);
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
            console.log("FiscalPrinter:: Desconectada");
        } catch (error) {
            console.error("FiscalPrinter:: Error al desconectar", error);
        }
    },

    /**
     * Intenta sincronizar pedidos pendientes del buffer offline
     */
    async _flushPendingOrders() {
        const buffer = LocalOrderBuffer.getAll();
        
        if (buffer.length === 0) return;
        
        console.log(`FiscalPrinter:: Intentando sincronizar ${buffer.length} pedidos offline...`);
        
        for (let i = buffer.length - 1; i >= 0; i--) {
            const entry = buffer[i];
            
            try {
                await this.orm.call("pos.order", "create_from_ui", [[{
                    'data': entry.orderData
                }]]);
                
                LocalOrderBuffer.remove(i);
                console.log(`FiscalPrinter:: Pedido offline #${i} sincronizado`);
                
            } catch (error) {
                entry.retries = (entry.retries || 0) + 1;
                console.warn(`FiscalPrinter:: Pedido offline #${i} falló (intento ${entry.retries}):`, error.message);
                
                if (entry.retries >= 5) {
                    LocalOrderBuffer.remove(i);
                    console.error(`FiscalPrinter:: Pedido offline #${i} abandonado`);
                }
            }
        }
        
        const remaining = LocalOrderBuffer.count();
        if (remaining === 0) {
            console.log("FiscalPrinter:: Todos los pedidos offline sincronizados");
        }
    },
});
