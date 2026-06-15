/** @odoo-module */

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { FiscalProtocol } from "../../core/FiscalProtocol";
import { StatusParser } from "../../core/StatusParser";
import { _t } from "@web/core/l10n/translation";

/**
 * FiscalDebuggerPopup - Herramienta de debugging para impresoras fiscales TFHKA
 * 
 * Funcionalidades:
 * - Monitor de tramas en tiempo real (log de comandos enviados/recibidos)
 * - Parser visual de Status (STS1/STS2)
 * - Consola de comandos raw para testing
 * - Gestor de banderas (flags)
 * 
 * Acceso: Solo para usuarios con debug mode activo
 */
export class FiscalDebuggerPopup extends AbstractAwaitablePopup {
    static template = "l10n_ve_pos_mf.FiscalDebuggerPopup";
    static defaultProps = {
        title: _t("Fiscalizador - Debugger de Máquina Fiscal"),
    };

    setup() {
        super.setup();
        
        this.state = useState({
            // Tab activo
            activeTab: "monitor", // monitor, status, console, flags
            
            // Monitor de tramas
            commandLog: [],
            autoScroll: true,
            
            // Status parser
            currentStatus: null,
            statusRefreshInterval: null,
            autoRefresh: false,
            
            // Consola de comandos
            rawCommand: "",
            rawResponse: "",
            
            // Flags
            flagNumber: "01",
            flagValue: "00",
        });

        // Referencia al driver
        this.fiscalPrinter = window.fiscalPrinter;

        onMounted(() => {
            this._initDebugger();
        });

        onWillUnmount(() => {
            this._cleanup();
        });
    }

    /**
     * Inicializa el debugger
     */
    async _initDebugger() {
        if (!this.fiscalPrinter || !this.fiscalPrinter.isConnected) {
            this.state.commandLog.push({
                timestamp: new Date().toISOString(),
                type: "error",
                message: "⚠️ Impresora no conectada. Conéctala desde el botón principal del POS."
            });
            return;
        }

        // Leer status inicial
        await this.refreshStatus();
        
        // Interceptar el método sendCommand del driver para capturar tramas
        this._patchDriverForLogging();
        
        this.state.commandLog.push({
            timestamp: new Date().toISOString(),
            type: "info",
            message: "✅ Fiscalizador inicializado correctamente"
        });
    }

    /**
     * Limpia recursos al cerrar
     */
    _cleanup() {
        if (this.state.statusRefreshInterval) {
            clearInterval(this.state.statusRefreshInterval);
        }
    }

    /**
     * Intercepta sendCommand del driver para logging
     */
    _patchDriverForLogging() {
        if (!this.fiscalPrinter || this.fiscalPrinter._debugPatched) {
            return;
        }

        const originalSendCommand = this.fiscalPrinter.sendCommand.bind(this.fiscalPrinter);
        
        this.fiscalPrinter.sendCommand = async (command, timeout) => {
            const startTime = Date.now();
            
            // Log comando enviado
            this._logCommand({
                direction: "sent",
                command: command,
                timestamp: new Date().toISOString()
            });

            // Ejecutar comando original
            const result = await originalSendCommand(command, timeout);
            
            const duration = Date.now() - startTime;
            
            // Log respuesta recibida
            this._logCommand({
                direction: "received",
                data: result.data,
                success: result.success,
                error: result.error,
                duration: duration,
                timestamp: new Date().toISOString()
            });

            return result;
        };

        this.fiscalPrinter._debugPatched = true;
    }

    /**
     * Registra un comando en el log
     */
    _logCommand(logEntry) {
        this.state.commandLog.push(logEntry);
        
        // Limitar a 100 entradas para no saturar memoria
        if (this.state.commandLog.length > 100) {
            this.state.commandLog.shift();
        }

        // Auto-scroll al final si está activo
        if (this.state.autoScroll) {
            this._scrollToBottom();
        }
    }

    /**
     * Hace scroll al final del log
     */
    _scrollToBottom() {
        setTimeout(() => {
            const logContainer = document.querySelector(".fiscal-debugger-log");
            if (logContainer) {
                logContainer.scrollTop = logContainer.scrollHeight;
            }
        }, 50);
    }

    // ========== ACCIONES DE LA UI ==========

    /**
     * Cambia de tab
     */
    switchTab(tab) {
        this.state.activeTab = tab;
        
        // Si se activa el tab de status, refrescar
        if (tab === "status" && !this.state.currentStatus) {
            this.refreshStatus();
        }
    }

    /**
     * Refresca el status de la impresora
     */
    async refreshStatus() {
        if (!this.fiscalPrinter || !this.fiscalPrinter.isConnected) {
            return;
        }

        try {
            const rawStatus = await this.fiscalPrinter.getStatus();
            
            if (rawStatus) {
                // Construir respuesta binaria simulada para el parser
                const sts1 = rawStatus.raw ? parseInt(rawStatus.raw.substring(0, 2), 16) : 0x60;
                const sts2 = rawStatus.raw ? parseInt(rawStatus.raw.substring(2, 4), 16) : 0x40;
                
                const mockResponse = new Uint8Array([
                    FiscalProtocol.STX,
                    sts1,
                    sts2,
                    FiscalProtocol.ETX,
                    0x00 // LRC (no importa para el parser)
                ]);
                
                this.state.currentStatus = StatusParser.parse(mockResponse);
            }
        } catch (error) {
            console.error("FiscalDebugger:: Error al leer status", error);
        }
    }

    /**
     * Activa/desactiva el auto-refresh del status
     */
    toggleAutoRefresh() {
        this.state.autoRefresh = !this.state.autoRefresh;
        
        if (this.state.autoRefresh) {
            this.state.statusRefreshInterval = setInterval(() => {
                this.refreshStatus();
            }, 2000); // Cada 2 segundos
        } else {
            if (this.state.statusRefreshInterval) {
                clearInterval(this.state.statusRefreshInterval);
                this.state.statusRefreshInterval = null;
            }
        }
    }

    /**
     * Envía un comando raw desde la consola
     */
    async sendRawCommand() {
        if (!this.fiscalPrinter || !this.fiscalPrinter.isConnected) {
            this.state.rawResponse = "Error: Impresora no conectada";
            return;
        }

        if (!this.state.rawCommand.trim()) {
            this.state.rawResponse = "Error: Comando vacío";
            return;
        }

        try {
            const result = await this.fiscalPrinter.sendCommand(this.state.rawCommand.trim());
            
            this.state.rawResponse = JSON.stringify({
                success: result.success,
                data: result.data,
                error: result.error
            }, null, 2);
        } catch (error) {
            this.state.rawResponse = `Error: ${error.message}`;
        }
    }

    /**
     * Ejecuta un comando de acceso rápido
     * @param {string} command - Comando a ejecutar (PJ, I0X, I0Z, 0, etc.)
     */
    async quickCommand(command) {
        this.state.rawCommand = command;
        await this.sendRawCommand();
    }

    /**
     * Envía un flag (bandera de configuración)
     */
    async sendFlag() {
        if (!this.fiscalPrinter || !this.fiscalPrinter.isConnected) {
            alert("Error: Impresora no conectada");
            return;
        }

        const flagCommand = `PJ${this.state.flagNumber}${this.state.flagValue}`;
        
        try {
            const result = await this.fiscalPrinter.sendCommand(flagCommand);
            
            if (result.success) {
                alert(`Flag ${this.state.flagNumber} configurado a valor ${this.state.flagValue}`);
            } else {
                alert(`Error al configurar flag: ${result.error}`);
            }
        } catch (error) {
            alert(`Error: ${error.message}`);
        }
    }

    /**
     * Limpia el log de comandos
     */
    clearLog() {
        this.state.commandLog = [];
    }

    /**
     * Exporta el log a un archivo de texto
     */
    exportLog() {
        const logText = this.state.commandLog.map(entry => {
            return `[${entry.timestamp}] ${entry.direction || entry.type}: ${entry.command || entry.message || entry.data}`;
        }).join('\n');

        const blob = new Blob([logText], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `fiscal_debugger_log_${Date.now()}.txt`;
        a.click();
        URL.revokeObjectURL(url);
    }

    /**
     * Cierra el popup
     */
    close() {
        this.props.close();
    }

    // ========== GETTERS PARA EL TEMPLATE ==========

    get hasConnection() {
        return this.fiscalPrinter && this.fiscalPrinter.isConnected;
    }

    get statusIndicators() {
        if (!this.state.currentStatus || !this.state.currentStatus.raw) {
            return null;
        }
        
        return StatusParser.getVisualIndicators(
            this.state.currentStatus.raw.sts1,
            this.state.currentStatus.raw.sts2
        );
    }
}
