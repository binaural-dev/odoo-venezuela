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
            
            // STS2 - Errores activos (flags booleanos)
            errorFlags: StatusParser.parseSTS2(sts2),
            
            // Lista de errores legibles
            errors: StatusParser.getErrorList(sts1, sts2),
            
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
     * Basado en sdk_tfhka/Tfhka.py líneas 389-482
     * 
     * IMPORTANTE: STS2 no usa máscara de bits simples. Los valores son códigos específicos.
     * 0x40 = SIN ERRORES (no significa error de papel!)
     * 
     * @param {number} sts2
     * @returns {Object}
     */
    static parseSTS2(sts2) {
        // Estados basados en valores exactos del SDK Python
        const isNoError = (sts2 === 0x40);
        const isPaperEnd = (sts2 === 0x41);           // Fin de papel
        const isPaperMechError = (sts2 === 0x42);     // Error mecánico de papel
        const isPaperBothError = (sts2 === 0x43);     // Ambos errores
        
        return {
            // Error crítico (valores específicos del SDK)
            criticalError: (sts2 === 0x64 || sts2 === 0x60 || sts2 === 0x6C),
            
            // Error de gaveta
            drawerError: Boolean(sts2 & 0x08),
            
            // Error del impresor (mecanismo)
            printerError: isPaperMechError || isPaperBothError,
            
            // Error en impresora (general)
            printerGeneralError: (sts2 >= 0x50), // Valores 0x50-0x6C son errores generales
            
            // Error de papel: solo si es 0x41, 0x42 o 0x43
            paperError: isPaperEnd || isPaperMechError || isPaperBothError,
            
            // Estados comunes
            noErrors: isNoError,
            hasPaperIssue: isPaperEnd || isPaperMechError || isPaperBothError,
            hasDrawerIssue: Boolean(sts2 & 0x08),
            
            // Códigos específicos del SDK
            memoryFull: (sts2 === 0x6C),        // Memoria fiscal llena
            fiscalError: (sts2 === 0x60),       // Error fiscal
            memoryError: (sts2 === 0x64),       // Error en memoria fiscal
            invalidCommand: (sts2 === 0x5C),    // Comando inválido
            noDirectives: (sts2 === 0x58),      // No hay directivas asignadas
            invalidRate: (sts2 === 0x54),       // Tasa inválida
            invalidValue: (sts2 === 0x50),      // Valor inválido
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
        if (errors.memoryFull) return "🔴 Memoria Fiscal Llena";
        if (errors.memoryError) return "❌ Error en Memoria Fiscal";
        if (errors.fiscalError) return "❌ Error Fiscal";
        if (errors.criticalError) return "❌ Error Crítico";
        if (errors.invalidCommand) return "⚠️ Comando Inválido";
        if (errors.invalidRate) return "⚠️ Tasa Inválida";
        if (errors.invalidValue) return "⚠️ Valor Inválido";
        if (errors.paperError) return "📄 Sin Papel";
        if (errors.printerError) return "⚠️ Error del Impresor";
        if (errors.drawerError) return "💰 Error de Gaveta";

        // Prioridad 2: Warnings de STS1
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
     * Genera una lista de errores activos en formato legible
     * @param {number} sts1
     * @param {number} sts2
     * @returns {Array<string>} Lista de mensajes de error
     */
    static getErrorList(sts1, sts2) {
        const errors = [];
        const state = StatusParser.parseSTS1(sts1);
        const errorFlags = StatusParser.parseSTS2(sts2);

        // Sin errores
        if (errorFlags.noErrors && !state.fiscalMemoryFull && !state.fiscalMemoryNearFull) {
            return errors; // Array vacío
        }

        // Errores críticos primero
        if (errorFlags.memoryFull) {
            errors.push("Memoria fiscal llena");
        }
        if (errorFlags.memoryError) {
            errors.push("Error en memoria fiscal");
        }
        if (errorFlags.fiscalError) {
            errors.push("Error fiscal");
        }
        if (errorFlags.criticalError) {
            errors.push("Error crítico de hardware");
        }
        if (errorFlags.paperError) {
            errors.push("Sin papel o papel atascado");
        }
        if (errorFlags.printerError) {
            errors.push("Error en el mecanismo de impresión");
        }
        if (errorFlags.drawerError) {
            errors.push("Gaveta abierta o con fallo");
        }

        // Warnings
        if (state.fiscalMemoryFull) {
            errors.push("Memoria fiscal llena");
        }
        if (state.fiscalMemoryNearFull) {
            errors.push("Memoria fiscal casi llena");
        }

        return errors;
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
