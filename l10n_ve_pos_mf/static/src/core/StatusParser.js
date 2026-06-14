/** @odoo-module */

/**
 * StatusParser - Parser de Status de impresoras fiscales TFHKA
 * 
 * Traduce los bytes de status (STS1 y STS2) recibidos del comando ENQ
 * a un objeto JavaScript con indicadores legibles.
 * 
 * Referencias:
 * - Manual TFHKA v8.4.2, Sección: "LEER ESTADO"
 * - STS1 (Estado): Bits 0-7 indican modo de operación
 * - STS2 (Error): Bits 0-7 indican errores activos
 */

export class StatusParser {
    
    /**
     * Parsea una respuesta de status (ENQ) de la impresora
     * @param {Uint8Array} response - Respuesta binaria del ENQ
     * @returns {Object} Status parseado con indicadores booleanos
     */
    static parse(response) {
        if (!response || response.length < 4) {
            return {
                error: "Respuesta de status incompleta",
                raw: null
            };
        }

        // La estructura de la respuesta es: STX + STS1 + STS2 + ETX + LRC
        // STS1 está en el índice 1, STS2 en el índice 2
        const sts1 = response[1];
        const sts2 = response[2];

        return {
            raw: { sts1, sts2 },
            rawHex: { sts1: sts1.toString(16).padStart(2, '0'), sts2: sts2.toString(16).padStart(2, '0') },
            
            // STS1 - Estado de la impresora
            state: StatusParser.parseSTS1(sts1),
            
            // STS2 - Errores activos
            errors: StatusParser.parseSTS2(sts2),
            
            // Helpers
            isOperational: StatusParser.isOperational(sts1, sts2),
            hasErrors: StatusParser.hasErrors(sts2),
            statusText: StatusParser.getStatusText(sts1, sts2)
        };
    }

    /**
     * Parsea el byte STS1 (Estado de la impresora)
     * @param {number} sts1
     * @returns {Object}
     */
    static parseSTS1(sts1) {
        return {
            // Bit 2: Modo Fiscal activo
            fiscalMode: Boolean(sts1 & 0x04),
            
            // Bit 3: Memoria Fiscal cercana a agotarse
            fiscalMemoryNearFull: Boolean(sts1 & 0x08),
            
            // Bit 4: Memoria Fiscal llena
            fiscalMemoryFull: Boolean(sts1 & 0x10),
            
            // Bit 5: Buffer de comandos lleno
            bufferFull: Boolean(sts1 & 0x20),
            
            // Bit 6: Transacción no fiscal en curso
            nonFiscalTransactionInProgress: Boolean(sts1 & 0x40),
            
            // Bit 7: Transacción fiscal en curso
            fiscalTransactionInProgress: Boolean(sts1 & 0x80),
            
            // Estados comunes (valores exactos del byte)
            isTrainingMode: (sts1 === 0x40), // Modo entrenamiento, en espera
            isFiscalReady: (sts1 === 0x64 || sts1 === 0x60), // Modo fiscal, en espera
            isFiscalInTransaction: (sts1 === 0x65 || sts1 === 0x61), // Modo fiscal, transacción activa
        };
    }

    /**
     * Parsea el byte STS2 (Errores de la impresora)
     * @param {number} sts2
     * @returns {Object}
     */
    static parseSTS2(sts2) {
        return {
            // Bit 2: Error crítico
            criticalError: Boolean(sts2 & 0x04),
            
            // Bit 3: Error de gaveta (abierta o con fallo)
            drawerError: Boolean(sts2 & 0x08),
            
            // Bit 4: Error del impresor (mecanismo)
            printerError: Boolean(sts2 & 0x10),
            
            // Bit 5: Error en impresora (general)
            printerGeneralError: Boolean(sts2 & 0x20),
            
            // Bit 6: Error de papel (sin papel o atascado)
            paperError: Boolean(sts2 & 0x40),
            
            // Estados comunes
            noErrors: (sts2 === 0x40), // Sin errores
            hasPaperIssue: (sts2 === 0x41 || Boolean(sts2 & 0x40)),
            hasDrawerIssue: (sts2 === 0x48 || Boolean(sts2 & 0x08)),
        };
    }

    /**
     * Verifica si la impresora está operativa (sin errores críticos)
     * @param {number} sts1
     * @param {number} sts2
     * @returns {boolean}
     */
    static isOperational(sts1, sts2) {
        const errors = StatusParser.parseSTS2(sts2);
        
        // No operativa si hay errores críticos o de papel
        if (errors.criticalError || errors.paperError || errors.printerError) {
            return false;
        }
        
        // No operativa si la memoria fiscal está llena
        const state = StatusParser.parseSTS1(sts1);
        if (state.fiscalMemoryFull) {
            return false;
        }
        
        return true;
    }

    /**
     * Verifica si hay algún error activo
     * @param {number} sts2
     * @returns {boolean}
     */
    static hasErrors(sts2) {
        return sts2 !== 0x40; // 0x40 = sin errores
    }

    /**
     * Obtiene un texto descriptivo del estado actual
     * @param {number} sts1
     * @param {number} sts2
     * @returns {string}
     */
    static getStatusText(sts1, sts2) {
        const state = StatusParser.parseSTS1(sts1);
        const errors = StatusParser.parseSTS2(sts2);

        // Prioridad 1: Errores críticos
        if (errors.criticalError) return "❌ Error Crítico";
        if (errors.paperError) return "📄 Sin Papel";
        if (errors.printerError) return "⚠️ Error del Impresor";
        if (errors.drawerError) return "💰 Error de Gaveta";

        // Prioridad 2: Warnings
        if (state.fiscalMemoryFull) return "🔴 Memoria Fiscal Llena";
        if (state.fiscalMemoryNearFull) return "🟡 Memoria Fiscal Casi Llena";
        if (state.bufferFull) return "⏳ Buffer Lleno";

        // Prioridad 3: Estados operativos
        if (state.fiscalTransactionInProgress) return "📝 Transacción Fiscal en Curso";
        if (state.nonFiscalTransactionInProgress) return "📄 Transacción No Fiscal en Curso";
        if (state.isFiscalReady) return "✅ Modo Fiscal - Lista";
        if (state.isTrainingMode) return "🎓 Modo Entrenamiento";

        return "🟢 Operativa";
    }

    /**
     * Genera indicadores visuales para la UI (colores de semáforo)
     * @param {number} sts1
     * @param {number} sts2
     * @returns {Object} Indicadores con color y estado
     */
    static getVisualIndicators(sts1, sts2) {
        const state = StatusParser.parseSTS1(sts1);
        const errors = StatusParser.parseSTS2(sts2);

        return {
            overall: {
                status: StatusParser.isOperational(sts1, sts2) ? "success" : "danger",
                color: StatusParser.isOperational(sts1, sts2) ? "#28a745" : "#dc3545",
                icon: StatusParser.isOperational(sts1, sts2) ? "✅" : "❌"
            },
            fiscalMode: {
                status: state.fiscalMode ? "success" : "warning",
                color: state.fiscalMode ? "#28a745" : "#ffc107",
                text: state.fiscalMode ? "Modo Fiscal" : "Modo Entrenamiento",
                icon: state.fiscalMode ? "🔒" : "🎓"
            },
            paper: {
                status: errors.paperError ? "danger" : "success",
                color: errors.paperError ? "#dc3545" : "#28a745",
                text: errors.paperError ? "Sin Papel" : "Papel OK",
                icon: errors.paperError ? "📄❌" : "📄✅"
            },
            drawer: {
                status: errors.drawerError ? "warning" : "success",
                color: errors.drawerError ? "#ffc107" : "#28a745",
                text: errors.drawerError ? "Gaveta Abierta/Error" : "Gaveta OK",
                icon: errors.drawerError ? "💰⚠️" : "💰✅"
            },
            memory: {
                status: state.fiscalMemoryFull ? "danger" : (state.fiscalMemoryNearFull ? "warning" : "success"),
                color: state.fiscalMemoryFull ? "#dc3545" : (state.fiscalMemoryNearFull ? "#ffc107" : "#28a745"),
                text: state.fiscalMemoryFull ? "Memoria Llena" : (state.fiscalMemoryNearFull ? "Memoria Casi Llena" : "Memoria OK"),
                icon: state.fiscalMemoryFull ? "💾🔴" : (state.fiscalMemoryNearFull ? "💾🟡" : "💾✅")
            },
            printer: {
                status: errors.printerError ? "danger" : "success",
                color: errors.printerError ? "#dc3545" : "#28a745",
                text: errors.printerError ? "Error Impresor" : "Impresor OK",
                icon: errors.printerError ? "🖨️❌" : "🖨️✅"
            }
        };
    }
}
