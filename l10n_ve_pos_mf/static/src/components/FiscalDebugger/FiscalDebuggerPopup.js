/** @odoo-module */

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { AbstractAwaitablePopup } from "@point_of_sale/app/popup/abstract_awaitable_popup";
import { FiscalProtocol } from "@l10n_ve_mf_base/core/FiscalProtocol";
import { StatusParser } from "@l10n_ve_mf_base/core/StatusParser";
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
            activeTab: "monitor", // monitor, status, s3, console, flags
            
            // Monitor de tramas
            commandLog: [],
            autoScroll: true,
            
            // Status parser
            currentStatus: null,
            statusRefreshInterval: null,
            autoRefresh: false,

            // Diagnóstico S3
            s3Data: null,
            s3Error: "",
            
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
     * Inicializa el debugger. A diferencia del resto del código (que abre y
     * cierra el puerto por cada operación vía `withConnection`), este
     * popup es una sesión interactiva — mantiene el puerto abierto mientras
     * esté abierto (vía `acquireConnection`/`releaseConnection`, que
     * comparten el mismo contador de referencias), para no reconectar en
     * cada click de la consola de comandos.
     */
    async _initDebugger() {
        if (!this.fiscalPrinter) {
            this.state.commandLog.push({
                timestamp: new Date().toISOString(),
                type: "error",
                message: "⚠️ No hay máquina fiscal configurada en esta caja."
            });
            return;
        }

        try {
            await this.fiscalPrinter.acquireConnection();
            this._connectionAcquired = true;
        } catch (error) {
            this.state.commandLog.push({
                timestamp: new Date().toISOString(),
                type: "error",
                message: `⚠️ No se pudo conectar con la máquina fiscal: ${error.message}`
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
        if (this._connectionAcquired && this.fiscalPrinter) {
            this._connectionAcquired = false;
            this.fiscalPrinter.releaseConnection();
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
        
        this.fiscalPrinter.sendCommand = async (command, timeout, ...rest) => {
            const startTime = Date.now();
            
            // Log comando enviado
            this._logCommand({
                direction: "sent",
                command: command,
                timestamp: new Date().toISOString()
            });

            // Ejecutar comando original
            const result = await originalSendCommand(command, timeout, ...rest);
            
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

        // Si se activa el tab S3, leer tasas/flags
        if (tab === "s3" && !this.state.s3Data) {
            this.refreshS3Data();
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
            // getStatus() ya retorna el objeto parseado por StatusParser
            const status = await this.fiscalPrinter.getStatus();
            
            if (status) {
                this.state.currentStatus = status;
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
     * Lee y parsea diagnóstico S3 (tasas y flags)
     */
    async refreshS3Data() {
        if (!this.fiscalPrinter || !this.fiscalPrinter.isConnected) {
            this.state.s3Error = "Impresora no conectada";
            this.state.s3Data = null;
            return;
        }

        if (typeof this.fiscalPrinter.readS3Data !== "function") {
            this.state.s3Error = "El driver actual no soporta lectura S3";
            this.state.s3Data = null;
            return;
        }

        try {
            this.state.s3Error = "";
            const result = await this.fiscalPrinter.readS3Data();
            if (!result.success) {
                this.state.s3Error = result.error || "No se pudo leer S3";
                this.state.s3Data = null;
                return;
            }

            this.state.s3Data = result.data;
        } catch (error) {
            this.state.s3Error = error.message || "Error inesperado leyendo S3";
            this.state.s3Data = null;
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
            this.state.rawResponse = "Enviando comando...";
            
            const result = await this.fiscalPrinter.sendCommand(this.state.rawCommand.trim());
            
            if (result.success) {
                this.state.rawResponse = JSON.stringify({
                    success: true,
                    data: result.data,
                    message: "Comando ejecutado correctamente"
                }, null, 2);
            } else {
                // Mostrar error con formato claro
                this.state.rawResponse = JSON.stringify({
                    success: false,
                    error: result.error,
                    help: this._getErrorHelp(result.error)
                }, null, 2);
            }
        } catch (error) {
            this.state.rawResponse = `Error: ${error.message}`;
        }
    }

    /**
     * Devuelve ayuda contextual según el error
     * @private
     */
    _getErrorHelp(error) {
        if (error.includes("Sin papel") || error.includes("paper")) {
            return "Verifica que haya papel en la impresora y que esté bien insertado.";
        }
        if (error.includes("Tapa abierta") || error.includes("cover")) {
            return "Cierra la tapa de la impresora correctamente.";
        }
        if (error.includes("Memoria fiscal llena")) {
            return "La memoria fiscal está llena. Contacta al servicio técnico.";
        }
        if (error.includes("Error de hardware")) {
            return "Apaga y enciende la impresora. Si persiste, contacta servicio técnico.";
        }
        return "Revisa el manual de la impresora o contacta soporte técnico.";
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
     * Test de conexión básico - envía ENQ y verifica respuesta
     */
    async testConnection() {
        if (!this.fiscalPrinter || !this.fiscalPrinter.isConnected) {
            this.state.rawResponse = "Error: Impresora no conectada";
            return;
        }

        try {
            this.state.rawResponse = "🔍 Probando conexión serial...\n\n";
            
            // Test 1: Verificar que el puerto está abierto
            this.state.rawResponse += "✓ Puerto serial abierto\n";
            
            // Test 2: Enviar ENQ (comando más simple)
            this.state.rawResponse += "📡 Enviando ENQ (consulta de status)...\n";
            const status = await this.fiscalPrinter.getStatus();
            
            if (status) {
                this.state.rawResponse += "✓ Respuesta recibida!\n\n";
                this.state.rawResponse += `Status: ${status.statusText}\n`;
                this.state.rawResponse += `STS1: 0x${status.rawHex.sts1}\n`;
                this.state.rawResponse += `STS2: 0x${status.rawHex.sts2}\n\n`;
                
                if (status.errors.length > 0) {
                    this.state.rawResponse += "⚠️ ERRORES DETECTADOS:\n";
                    status.errors.forEach(err => {
                        this.state.rawResponse += `  - ${err}\n`;
                    });
                } else {
                    this.state.rawResponse += "✅ SIN ERRORES - Impresora lista\n";
                }
                
                this.state.rawResponse += "\n🎉 CONEXIÓN EXITOSA - La impresora responde correctamente";
            } else {
                this.state.rawResponse += "❌ NO SE RECIBIÓ RESPUESTA\n\n";
                this.state.rawResponse += "Posibles causas:\n";
                this.state.rawResponse += "1. Cable USB desconectado o dañado\n";
                this.state.rawResponse += "2. Baudrate incorrecto (debe ser 9600)\n";
                this.state.rawResponse += "3. Impresora apagada\n";
                this.state.rawResponse += "4. Hub USB con problemas (prueba conexión directa)\n";
                this.state.rawResponse += "5. Puerto serial incorrecto\n\n";
                this.state.rawResponse += "💡 Revisa el cable y prueba conectar directamente sin hub USB";
            }
        } catch (error) {
            this.state.rawResponse = `❌ ERROR AL PROBAR CONEXIÓN:\n\n${error.message}\n\n`;
            this.state.rawResponse += "Verifica:\n";
            this.state.rawResponse += "- Cable USB conectado\n";
            this.state.rawResponse += "- Impresora encendida\n";
            this.state.rawResponse += "- Puerto serial correcto\n";
        }
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
