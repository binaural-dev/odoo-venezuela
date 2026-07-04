/** @odoo-module */

import { SerialConnection } from "../core/SerialConnection";
import { FiscalProtocol } from "../core/FiscalProtocol";

/**
 * TfhkaDriver - Driver de alto nivel para impresoras fiscales The Factory HKA
 * 
 * Implementa los comandos específicos del protocolo TFHKA basados en:
 * Manual de Protocolos y Comandos v8.4.2 - Venezuela
 * 
 * TIPOS DE COMANDOS:
 * 
 * 1. Comandos de IMPRESIÓN (esperan ACK, imprimen asincrónicamente):
 *    - D: Imprimir Programación (tasas, flags, cajeros, firmware)
 *    - I0X: Reporte X (consulta sin cerrar día)
 *    - I0Z: Reporte Z (cierre fiscal del día)
 *    - 0: Abrir gaveta
 *    - I01, I02, I03: Facturas y notas
 * 
 * 2. Comandos de DATOS (esperan trama con datos):
 *    - S1: Identificación de impresora
 *    - S2: Totales del documento actual
 *    - S3: Tasas de impuesto y flags
 *    - S4: Medios de pago
 *    - S5-S8P: Otros datos de status
 *    - U0X, U0Z: Extracción de reportes (datos, no impresión)
 * 
 * 3. Comandos de CONFIGURACIÓN (esperan ACK):
 *    - PJnnvv: Escribir flag (nn=número flag 00-99, vv=valor 00-99)
 *    - Otros comandos de setup
 * 
 * 4. Comando de STATUS (formato especial):
 *    - ENQ (0x05): Consulta estado (responde con 5 bytes: STX|STS1|STS2|ETX|LRC)
 */

export class TfhkaDriver {
    
    constructor() {
        this.connection = new SerialConnection();
        this.isConnected = false;
        this.lastStatus = null;
        this.retryAttempts = 3;
        this.retryDelay = 500; // ms
    }

    _isWaitingState(sts1) {
        return [0x40, 0x60, 0x64].includes(sts1);
    }

    _isTransactionState(sts1) {
        return [0x41, 0x61, 0x65, 0x62, 0x42].includes(sts1);
    }

    _formatSts(sts1) {
        return typeof sts1 === "number" ? `0x${sts1.toString(16)}` : "N/A";
    }

    /**
     * Conecta con la impresora fiscal
     * @returns {Promise<boolean>}
     */
    async connect() {
        try {
            // Intentar reconexión automática primero
            let connected = await this.connection.autoConnect();
            
            // Si falla, solicitar permiso al usuario
            if (!connected) {
                connected = await this.connection.requestPort();
            }
            
            if (connected) {
                // Verificar que la impresora responda
                const status = await this.getStatus();
                this.isConnected = status !== null;
                return this.isConnected;
            }
            
            return false;
        } catch (error) {
            console.error("TfhkaDriver:: Error al conectar", error);
            return false;
        }
    }

    /**
     * Desconecta la impresora fiscal
     * @returns {Promise<void>}
     */
    async disconnect() {
        await this.connection.disconnect();
        this.isConnected = false;
    }

    /**
     * Envía un comando y espera respuesta (con reintentos en caso de NAK)
     * @param {string} command - Comando ASCII
     * @param {number} timeout - Timeout en ms
     * @param {boolean} checkStatus - Verificar status antes de enviar (default: true)
     * @param {boolean} skipFlush - Saltar flushBuffer (para comandos dentro de una transacción)
     * @returns {Promise<Object>} - { success: boolean, data: string, error: string }
     */
    async sendCommand(command, timeout = null, checkStatus = true, skipFlush = false) {
        if (!this.isConnected) {
            return { success: false, data: "", error: "Impresora no conectada" };
        }

        const skipStatusCheck = ['9', '199', 'w'].includes(command);
        if (checkStatus && command !== 'ENQ' && !skipStatusCheck) {
            const status = await this.getStatus();
            if (!status) {
                return { success: false, data: "", error: "No se pudo leer el estado de la impresora" };
            }

            if (status.errors && status.errors.length > 0) {
                const errorMsg = status.errors.join(', ');
                console.error("TfhkaDriver:: Impresora tiene errores:", errorMsg);
                return { success: false, data: "", error: `Error de impresora: ${errorMsg}` };
            }

            const sts1 = status.raw?.sts1;
            const isWaiting = this._isWaitingState(sts1);
            const isInTransaction = this._isTransactionState(sts1);

            if (isInTransaction) {
                console.warn("TfhkaDriver:: Impresora tiene transacción abierta (STS1:", this._formatSts(sts1), "). Intentando abortar...");
                const aborted = await this.abortTransaction();
                if (!aborted) {
                    return {
                        success: false,
                        data: "",
                        error: `Impresora ocupada (STS1=${this._formatSts(sts1)}). Transacción previa no pudo ser cancelada. Reinicia la impresora.`
                    };
                }
            } else if (!isWaiting && sts1 !== undefined) {
                console.warn("TfhkaDriver:: Estado inesperado STS1:", this._formatSts(sts1), "- continuando de todas formas");
            }
        }

        if (timeout === null) {
            if (command.startsWith('PJ')) {
                timeout = 60000;
            } else if (command.startsWith('I0X') || command.startsWith('I0Z')) {
                timeout = 30000;
            } else if (command === '101' || command === '199' || command === '3') {
                timeout = 15000;
            } else {
                timeout = 5000;
            }
        }

        const isHeavyCommand = command === '101' || command === '199' || command === '3' || command.startsWith('2');
        const cmdDelay = isHeavyCommand ? 500 : 100;

        for (let attempt = 0; attempt < this.retryAttempts; attempt++) {
            try {
                if (attempt === 0 && !skipFlush) {
                    await this.connection.flushBuffer();
                }

                const frame = FiscalProtocol.buildFrame(command);

                const sent = await this.connection.write(frame);
                if (!sent) {
                    throw new Error("Error al escribir en puerto serial");
                }

                await new Promise(resolve => setTimeout(resolve, cmdDelay));

                const response = await this.connection.read(timeout);
                if (!response) {
                    throw new Error("No se recibió respuesta de la impresora");
                }

                if (FiscalProtocol.isACK(response)) {
                    return { success: true, data: "ACK", error: "" };
                }

                if (FiscalProtocol.isNAK(response)) {
                    console.warn(`TfhkaDriver:: NAK recibido, reintentando...`);
                    await new Promise(resolve => setTimeout(resolve, this.retryDelay));
                    continue;
                }

                const parsed = FiscalProtocol.parseResponse(response);
                if (parsed.valid) {
                    return { success: true, data: parsed.data, error: "" };
                } else {
                    return { success: false, data: "", error: parsed.error };
                }

            } catch (error) {
                console.error(`TfhkaDriver:: Error en intento ${attempt + 1}:`, error);
                if (attempt < this.retryAttempts - 1) {
                    await new Promise(resolve => setTimeout(resolve, this.retryDelay));
                }
            }
        }

        return { success: false, data: "", error: "Máximo de reintentos alcanzado" };
    }

    /**
     * Aborta una transacción fiscal que quedó abierta
     * Se usa para recuperar la impresora cuando un intento anterior falló a mitad
     * @returns {Promise<boolean>} - true si se abortó exitosamente
     */
    async abortTransaction() {
        try {
            const statusBefore = await this.getStatus();
            const stsBefore = statusBefore?.raw?.sts1;
            if (this._isWaitingState(stsBefore)) {
                return true;
            }
            
            await this.connection.flushBuffer();

            // Intentar cancelar el documento actual con "9" (Anular Documento)
            const frame9 = FiscalProtocol.buildFrame("9");
            await this.connection.write(frame9);
            const response9 = await this.connection.read(3000);
            
            if (response9 && FiscalProtocol.isACK(response9)) {
                await new Promise(resolve => setTimeout(resolve, 500));
                return true;
            }

            const statusAfter9 = await this.getStatus();
            const stsAfter9 = statusAfter9?.raw?.sts1;
            if (this._isWaitingState(stsAfter9)) {
                return true;
            }

            // Si "9" no funcionó, intentar con "199" (Fin de Documento)
            console.warn("TfhkaDriver:: Comando 9 no respondió, intentando 199...");
            const frame199 = FiscalProtocol.buildFrame("199");
            await this.connection.write(frame199);
            const response199 = await this.connection.read(3000);

            if (response199 && FiscalProtocol.isACK(response199)) {
                await new Promise(resolve => setTimeout(resolve, 500));
                return true;
            }

            // Verificar si la impresora ya está en reposo después de los intentos
            await new Promise(resolve => setTimeout(resolve, 1000));
            const statusCheck = await this.getStatus();
            if (statusCheck) {
                const sts1 = statusCheck.raw?.sts1;
                const isNowWaiting = this._isWaitingState(sts1);
                if (isNowWaiting) {
                    return true;
                }
                console.error("TfhkaDriver:: Abort falló. STS1 actual:", this._formatSts(sts1));
            }

            console.error("TfhkaDriver:: No se pudo abortar la transacción");
            return false;

        } catch (error) {
            console.error("TfhkaDriver:: Error al abortar transacción:", error);
            return false;
        }
    }

    /**
     * Consulta el estado de la impresora (comando ENQ)
     * @returns {Promise<Object|null>} - Estado parseado o null si falla
     */
    async getStatus() {
        try {
            // Limpiar buffer antes de enviar ENQ
            await this.connection.flushBuffer();
            
            const enqFrame = new Uint8Array([FiscalProtocol.ENQ]);
            await this.connection.write(enqFrame);
            
            // Esperar 50ms como hace el SDK Python
            await new Promise(resolve => setTimeout(resolve, 50));
            
            // Leer exactamente 5 bytes (formato ENQ: STX|STS1|STS2|ETX|LRC)
            const response = await this.connection.read(500); // Timeout corto para ENQ
            if (!response) {
                console.error("TfhkaDriver:: No se recibió respuesta al ENQ");
                return null;
            }

            // Parsear respuesta ENQ (formato especial, no es un frame normal)
            const status = FiscalProtocol.parseStatusENQ(response);
            this.lastStatus = status;
            return status;
        } catch (error) {
            console.error("TfhkaDriver:: Error al leer estado", error);
            return null;
        }
    }

    /**
     * Imprime Reporte X (consulta sin cerrar día)
     * @returns {Promise<Object>}
     */
    async printReportX() {
        return await this.sendCommand("I0X");
    }

    /**
     * Imprime Reporte Z (cierre diario)
     * @returns {Promise<Object>}
     */
    async printReportZ() {
        return await this.sendCommand("I0Z");
    }

    /**
     * Abre la gaveta de dinero
     * @returns {Promise<Object>}
     */
    async openDrawer() {
        return await this.sendCommand("0");
    }

    /**
     * Reimprime un documento fiscal ya emitido (paridad con flujo IoT legacy).
     *
     * Comandos TFHKA:
     * - RF: reimpresión de facturas (out_invoice, incluye ND emitidas por diario débito)
     * - RC: reimpresión de notas de crédito (out_refund)
     *
     * Formato legacy: MODE + número.zfill(7) + número.zfill(7) (rango desde/hasta).
     *
     * @param {Object} params
     * @param {string} params.type - Tipo de documento Odoo ("out_invoice" | "out_refund")
     * @param {string|number} params.number - Número fiscal del documento (mf_invoice_number)
     * @returns {Promise<Object>} - { success: boolean, data: string, error: string }
     */
    async reprintDocument({ type, number }) {
        if (!this.isConnected) {
            return { success: false, data: "", error: "Impresora no conectada" };
        }

        const MODES = {
            out_invoice: "RF",
            out_refund: "RC",
        };
        const mode = MODES[type];
        if (!mode) {
            return { success: false, data: "", error: `Tipo de documento no soportado para reimpresión: ${type}` };
        }

        const cleaned = String(number || "").replace(/[^0-9]/g, "");
        if (!cleaned) {
            return { success: false, data: "", error: "Número fiscal inválido para reimpresión" };
        }

        const n = cleaned.padStart(7, "0");
        const command = `${mode}${n}${n}`;

        // La reimpresión puede tardar (imprime el documento completo)
        const result = await this.sendCommand(command, 30000);
        if (!result.success) {
            return { success: false, data: "", error: result.error || "Error al reimprimir documento" };
        }

        return { success: true, data: "Documento reimpreso correctamente", error: "" };
    }

    /**
     * Imprime una factura completa
     * @param {Object} order - Objeto con los datos de la orden de Odoo POS
     * @returns {Promise<Object>} - { success: boolean, invoiceNumber: string, error: string }
     */
    async printInvoice(order) {
        try {
            // 1. Datos del cliente (RIF/CI)
            if (order.partner && order.partner.vat) {
                const rifCommand = `@${order.partner.vat}`;
                const result = await this.sendCommand(rifCommand);
                if (!result.success) {
                    return { success: false, invoiceNumber: "", error: `Error enviando RIF: ${result.error}` };
                }
            }

            // 2. Razón social del cliente
            if (order.partner && order.partner.name) {
                const nameCommand = `A${order.partner.name}`;
                const result = await this.sendCommand(nameCommand);
                if (!result.success) {
                    return { success: false, invoiceNumber: "", error: `Error enviando nombre: ${result.error}` };
                }
            }

            // 3. Registrar productos (líneas de la orden)
            for (const line of order.lines) {
                // Formato del comando de producto:
                // ! [Código] [Descripción] * [Cantidad] [Precio Unitario] [# Dpto]
                const quantity = this._formatQuantity(line.qty);
                const price = this._formatAmount(line.price_unit);
                const description = line.product_id.display_name.substring(0, 30); // Max 30 chars
                const deptCode = "01"; // Departamento por defecto (ajustar según configuración)

                const productCommand = `!${description}*${quantity}${price}${deptCode}`;
                const result = await this.sendCommand(productCommand);
                
                if (!result.success) {
                    // Si falla, cancelar la factura
                    await this.sendCommand("z"); // Comando de cancelar factura
                    return { success: false, invoiceNumber: "", error: `Error registrando producto: ${result.error}` };
                }
            }

            // 4. Descuentos globales (si aplica)
            if (order.total_discount > 0) {
                const discountAmount = this._formatAmount(order.total_discount);
                const discountCommand = `m-${discountAmount}`;
                await this.sendCommand(discountCommand);
            }

            // 5. Totalización (cerrar factura con pago)
            // Comando 1: Pago directo (asigna todo el monto al medio de pago)
            const paymentMethod = this._getPaymentMethodCode(order.payment_ids);
            const totalizeCommand = `1${paymentMethod}`;
            const totalizeResult = await this.sendCommand(totalizeCommand);

            if (!totalizeResult.success) {
                return { success: false, invoiceNumber: "", error: `Error totalizando: ${totalizeResult.error}` };
            }

            // 6. Leer el estado para obtener el número de factura
            const status = await this.getStatus();
            const invoiceNumber = status ? this._extractInvoiceNumber(status) : "";

            return { 
                success: true, 
                invoiceNumber: invoiceNumber, 
                error: "" 
            };

        } catch (error) {
            console.error("TfhkaDriver:: Error imprimiendo factura", error);
            // Intentar cancelar la factura en caso de error
            await this.sendCommand("z");
            return { success: false, invoiceNumber: "", error: error.message };
        }
    }

    /**
     * Imprime una Nota de Crédito (devolución)
     * @param {Object} order - Objeto con los datos de la orden
     * @returns {Promise<Object>}
     */
    async printCreditNote(order) {
        try {
            // Comando para abrir nota de crédito: I02
            const openResult = await this.sendCommand("I02");
            if (!openResult.success) {
                return { success: false, error: `Error abriendo nota de crédito: ${openResult.error}` };
            }

            // Similar a printInvoice pero con comando I02
            // TODO: Implementar lógica completa de nota de crédito
            // Requiere: número de factura afectada, serial, fecha, etc.

            return { success: true, error: "" };
        } catch (error) {
            console.error("TfhkaDriver:: Error imprimiendo nota de crédito", error);
            return { success: false, error: error.message };
        }
    }

    // ========== UTILIDADES PRIVADAS ==========

    /**
     * Formatea cantidad para el protocolo TFHKA
     * @param {number} qty
     * @returns {string} - Formato: 6 dígitos (4 enteros + 2 decimales)
     */
    _formatQuantity(qty) {
        const formatted = Math.round(qty * 100);
        return formatted.toString().padStart(6, '0');
    }

    /**
     * Formatea monto para el protocolo TFHKA
     * @param {number} amount
     * @returns {string} - Formato: 12 dígitos (10 enteros + 2 decimales)
     */
    _formatAmount(amount) {
        const formatted = Math.round(amount * 100);
        return formatted.toString().padStart(12, '0');
    }

    /**
     * Obtiene el código de medio de pago (01-24 según configuración)
     * @param {Array} payments
     * @returns {string} - Código de 2 dígitos
     */
    _getPaymentMethodCode(payments) {
        // TODO: Mapear desde configuración de Odoo
        // Por ahora, retornamos "01" (Efectivo) por defecto
        if (!payments || payments.length === 0) {
            return "01";
        }
        
        // Extraer el primer medio de pago
        const firstPayment = payments[0];
        // Mapeo básico (ajustar según configuración real)
        const paymentMap = {
            "cash": "01",
            "card": "02",
            "bank": "03",
        };
        
        return paymentMap[firstPayment.payment_method_id.type] || "01";
    }

    /**
     * Extrae el número de factura del status de la impresora
     * @param {Object} status
     * @returns {string}
     */
    _extractInvoiceNumber(status) {
        // TODO: Parsear el número de factura desde el status
        // La impresora TFHKA retorna el número en el status después de cerrar
        // Por ahora retornamos un placeholder
        return status.raw || "N/A";
    }

    _toCounter(value) {
        const cleaned = String(value || "").replace(/[^0-9]/g, "");
        if (!cleaned) {
            return null;
        }
        const parsed = parseInt(cleaned, 10);
        return Number.isNaN(parsed) ? null : parsed;
    }

    _parseS1Data(rawData) {
        if (!rawData) {
            return null;
        }

        const payload = String(rawData)
            .replace(/^\u0002/, "")
            .replace(/\u0003$/, "")
            .replace(/^S1/, "");

        const fields = payload
            .split("\n")
            .map((value) => value.replace(/\r/g, "").trim())
            .filter((value) => value.length > 0);

        if (fields.length < 10) {
            return null;
        }

        const shortFormat = fields.length <= 15;
        const parsed = {
            cashierNumber: fields[0] || "",
            lastInvoiceNumber: null,
            lastDebtNoteNumber: null,
            lastNCNumber: null,
            dailyClosureCounter: null,
            fiscalReportsCounter: null,
            rif: "",
            registeredMachineNumber: "",
            raw: fields,
        };

        if (shortFormat) {
            parsed.lastInvoiceNumber = this._toCounter(fields[2]);
            parsed.dailyClosureCounter = this._toCounter(fields[6]);
            parsed.fiscalReportsCounter = this._toCounter(fields[7]);
            parsed.rif = fields[8] || "";
            parsed.registeredMachineNumber = fields[9] || "";
            parsed.lastNCNumber = this._toCounter(fields[12]);
        } else {
            parsed.lastInvoiceNumber = this._toCounter(fields[2]);
            parsed.lastDebtNoteNumber = this._toCounter(fields[4]);
            parsed.lastNCNumber = this._toCounter(fields[6]);
            parsed.dailyClosureCounter = this._toCounter(fields[11]);
            parsed.rif = fields[12] || "";
            parsed.registeredMachineNumber = fields[13] || "";
        }

        return parsed;
    }

    async _readS1Data() {
        const response = await this.sendCommand("S1", 5000, false);
        if (!response.success) {
            return { success: false, data: null, error: response.error || "No se pudo leer S1" };
        }

        const data = this._parseS1Data(response.data);
        if (!data) {
            return {
                success: false,
                data: null,
                error: "No se pudo parsear la respuesta S1 de la impresora",
            };
        }

        return { success: true, data, error: "" };
    }

    _decodeImplicit2Decimals(rawValue) {
        const cleaned = String(rawValue || "").replace(/[^0-9]/g, "");
        if (!cleaned) {
            return 0;
        }

        if (cleaned.length <= 2) {
            return Number(cleaned) / 100;
        }

        const integer = Number(cleaned.slice(0, -2));
        const decimal = Number(cleaned.slice(-2)) / 100;
        return integer + decimal;
    }

    _getTaxTypeLabel(type) {
        if (String(type) === "1") {
            return "Excluido";
        }
        if (String(type) === "2") {
            return "Incluido";
        }
        return "No definido";
    }

    _parseS3RateLine(rawLine, removePrefix = false) {
        const line = removePrefix
            ? String(rawLine || "").replace(/^S3/, "")
            : String(rawLine || "");
        const type = line.charAt(0) || "";
        const value = this._decodeImplicit2Decimals(line.slice(1));

        return {
            type,
            typeLabel: this._getTaxTypeLabel(type),
            value,
        };
    }

    _parseS3Data(rawData) {
        if (!rawData) {
            return null;
        }

        const payload = String(rawData)
            .replace(/^\u0002/, "")
            .replace(/\u0003$/, "");

        const lines = payload
            .split("\n")
            .map((value) => value.replace(/\r/g, "").trim())
            .filter((value) => value.length > 0);

        if (lines.length < 4) {
            return null;
        }

        const tax1 = this._parseS3RateLine(lines[0], true);
        const tax2 = this._parseS3RateLine(lines[1]);
        const tax3 = this._parseS3RateLine(lines[2]);

        const tax4Line = String(lines[3] || "");
        const igtfType = tax4Line.charAt(0) || "";
        const numericTail = tax4Line.slice(1).replace(/[^0-9]/g, "");
        const igtfRaw = numericTail.slice(0, 4);
        const flagsRaw = numericTail.slice(4);
        const systemFlags = [];

        for (let i = 0; i + 1 < flagsRaw.length; i += 2) {
            const flag = parseInt(flagsRaw.slice(i, i + 2), 10);
            if (!Number.isNaN(flag)) {
                systemFlags.push(flag);
            }
        }

        return {
            tax1,
            tax2,
            tax3,
            igtf: {
                type: igtfType,
                typeLabel: this._getTaxTypeLabel(igtfType),
                value: this._decodeImplicit2Decimals(igtfRaw),
            },
            systemFlags,
            raw: lines,
        };
    }

    async readS3Data() {
        const response = await this.sendCommand("S3", 5000, false);
        if (!response.success) {
            return { success: false, data: null, error: response.error || "No se pudo leer S3" };
        }

        const data = this._parseS3Data(response.data);
        if (!data) {
            return {
                success: false,
                data: null,
                error: "No se pudo parsear la respuesta S3 de la impresora",
            };
        }

        return { success: true, data, error: "" };
    }

    _parseS4Data(rawData) {
        if (!rawData) {
            return null;
        }

        const payload = String(rawData)
            .replace(/^\u0002/, "")
            .replace(/\u0003$/, "")
            .replace(/^S4/, "");

        const lines = payload
            .split("\n")
            .map((value) => value.replace(/\r/g, "").trim())
            .filter((value) => value.length > 0);

        const methods = [];
        for (const line of lines) {
            const match = line.match(/^(\d{2})(.*)$/);
            if (match) {
                methods.push({
                    code: match[1],
                    name: match[2].trim(),
                    raw: line,
                });
            } else {
                methods.push({
                    code: "",
                    name: line,
                    raw: line,
                });
            }
        }

        return {
            methods,
            raw: lines,
        };
    }

    async readS4Data() {
        const response = await this.sendCommand("S4", 5000, false);
        if (!response.success) {
            return { success: false, data: null, error: response.error || "No se pudo leer S4" };
        }

        const data = this._parseS4Data(response.data);
        if (!data) {
            return {
                success: false,
                data: null,
                error: "No se pudo parsear la respuesta S4 de la impresora",
            };
        }

        return { success: true, data, error: "" };
    }

    _buildFiscalResponse(message, documentNumber, s1Data) {
        const invoiceNumber = documentNumber ? String(documentNumber) : "";
        const serial = s1Data?.registeredMachineNumber || "";
        const reportCounter = s1Data?.dailyClosureCounter;
        const reportZ = Number.isInteger(reportCounter) ? reportCounter + 1 : "";

        return {
            success: true,
            data: message,
            error: "",
            invoiceNumber,
            invoice_number: invoiceNumber,
            serial,
            serial_machine: serial,
            reportZ,
            mf_reportz: reportZ,
        };
    }

    // ============================================================================
    // MÉTODOS DE FACTURACIÓN (INVOICE, CREDIT NOTE, DEBIT NOTE)
    // ============================================================================

    /**
     * Formatea un número con ceros a la izquierda
     * @param {number} num - Número a formatear
     * @param {number} intPart - Dígitos de la parte entera
     * @param {number} decPart - Dígitos de la parte decimal
     * @returns {string} - Número formateado (ej: "0000010050" para 100.50)
     */
    _formatAmount(num, intPart, decPart) {
        const fixed = Number(num).toFixed(decPart);
        const [integer, decimal] = fixed.split('.');
        
        return integer.padStart(intPart, '0') + (decimal || '').padStart(decPart, '0');
    }

    /**
     * Mapea código de impuesto de Odoo a código TFHKA
     * @param {string} fiscalCode - Código fiscal (0=Exento, 1=General, 2=Reducido, 3=Adicional)
     * @returns {string} - Carácter TFHKA (" ", "!", '"', "#")
     */
    _getTaxCharacter(fiscalCode) {
        const normalizedCode = String(fiscalCode ?? "1").replace(/^t/i, "");
        const TAX_MAP = {
            "0": " ",   // Exento (0x20)
            "1": "!",   // Tasa 1 General (0x21)
            "2": '"',   // Tasa 2 Reducida (0x22)
            "3": "#"    // Tasa 3 Adicional (0x23)
        };
        
        return TAX_MAP[normalizedCode] || "!";
    }

    _appendHeaderInfo(commands, orderData) {
        let infoIndex = 0;

        if (orderData.partner?.address) {
            const addr = String(orderData.partner.address || "");
            const firstLine = addr.substring(0, 30);
            if (firstLine) {
                commands.push(`i${String(infoIndex).padStart(2, '0')}Direccion:${firstLine}`);
                infoIndex++;
            }

            const secondLine = addr.substring(30, 70);
            if (secondLine) {
                commands.push(`i${String(infoIndex).padStart(2, '0')}${secondLine}`);
                infoIndex++;
            }
        }

        if (orderData.partner?.phone) {
            commands.push(`i${String(infoIndex).padStart(2, '0')}Telefono:${orderData.partner.phone}`);
            infoIndex++;
        }

        for (const line of orderData.header_lines || []) {
            commands.push(`i${String(infoIndex).padStart(2, '0')}${String(line).substring(0, 127)}`);
            infoIndex++;
        }
    }

    _appendFooterInfo(commands, orderData) {
        const counter = { value: 0 };
        this._appendDiscountInfoLine(commands, orderData, counter);

        for (const line of orderData.footer_lines || []) {
            commands.push(`i${String(counter.value).padStart(2, '0')}${String(line).substring(0, 127)}`);
            counter.value++;
        }

        for (const line of orderData.additional_lines || []) {
            commands.push(`i${String(counter.value).padStart(2, '0')}${String(line).substring(0, 127)}`);
            counter.value++;
        }
    }

    /**
     * Emite UNA línea informativa sobre el descuento global aplicado.
     *
     * Solo se invoca para facturas (no para NC ni ND). El cálculo de la
     * tasa y del monto ya viene resuelto en el PosStore (`global_discount_rate`,
     * `global_discount_amount`, `global_clamped`). Aquí se formatea y se
     * infiere un índice `iXX` libre dentro del cupo de 10 líneas informativas.
     * Avanza `counter.value` para que el resto del pie de factura continúe con
     * índices consecutivos.
     *
     * @param {Array} commands - Buffer de comandos fiscales
     * @param {Object} orderData - Datos de la orden
     * @param {Object} counter - { value: number } mutable; índice actual
     * @returns {boolean} true si al menos una línea fue emitida
     */
    _appendDiscountInfoLine(commands, orderData, counter) {
        const rate = Number(orderData?.global_discount_rate || 0);
        const amount = Number(orderData?.global_discount_amount || 0);
        const clamped = Boolean(orderData?.global_clamped);

        if (!(rate > 0) || amount <= 0) {
            return false;
        }

        const MAX_INFO_LINES = 10;
        const startIndex = counter.value;
        if (startIndex >= MAX_INFO_LINES) {
            console.warn(
                `TfhkaDriver:: No hay slot libre para línea informativa de descuento global (slots usados: ${startIndex}/10)`
            );
            return false;
        }

        const amountStr = amount.toFixed(2);
        const text = `DESC. GLOBAL = ${amountStr}`;
        commands.push(`i${String(startIndex).padStart(2, '0')}${text.substring(0, 127)}`);
        counter.value++;

        if (clamped && counter.value < MAX_INFO_LINES) {
            commands.push(
                `i${String(counter.value).padStart(2, '0')}DESC. GLOBAL EXCEDIO SUBTOTAL`
            );
            counter.value++;
        }

        return true;
    }

    _appendPaymentCommands(commands, orderData, config) {
        const payments = orderData.payment_lines || [];
        const groupedPayments = {};

        if (orderData.has_cashbox) {
            commands.push("w");
        }

        for (const payment of payments) {
            const methodCode = String(payment.payment_method_code || "01").padStart(2, '0');
            const amount = Math.abs(Number(payment.amount || 0));
            groupedPayments[methodCode] = (groupedPayments[methodCode] || 0) + amount;
        }

        const paymentEntries = Object.entries(groupedPayments)
            .filter(([, amount]) => amount > 0)
            .map(([methodCode, amount]) => ({ methodCode, amount }));

        if (!paymentEntries.length) {
            commands.push("101");
            return;
        }

        const closingPayment = paymentEntries.reduce((max, current) =>
            current.amount > max.amount ? current : max
        );
        const closingMethod = closingPayment.methodCode;

        for (const { methodCode, amount } of paymentEntries) {
            if (methodCode === closingMethod) {
                continue;
            }
            const amountStr = this._formatAmount(
                amount,
                config.max_payment_amount_int,
                config.max_payment_amount_decimal
            );
            commands.push(`2${methodCode}${amountStr}`);
        }

        commands.push(`1${closingMethod}`);
    }

    /**
     * Imprime una factura fiscal (secuencia completa TFHKA)
     * @param {Object} orderData - Datos de la orden del POS
     * @param {Object} flag21Config - Configuración de formato numérico según flag 21
     * @returns {Promise<Object>} - { success: boolean, data: string, error: string }
     */
    async printInvoice(orderData, flag21Config = null) {
        if (!this.isConnected) {
            return { success: false, data: "", error: "Impresora no conectada" };
        }

        // Paso 0: Verificar que la impresora esté libre antes de empezar
        const statusBefore = await this.getStatus();
        if (!statusBefore) {
            return { success: false, data: "", error: "No se puede leer el estado de la impresora" };
        }

        const sts1Before = statusBefore.raw?.sts1;
        const isWaiting = this._isWaitingState(sts1Before);
        if (!isWaiting) {
            console.warn("TfhkaDriver:: Impresora no está en reposo (STS1=" + this._formatSts(sts1Before) + "), intentando abortar...");
            const aborted = await this.abortTransaction();
            if (!aborted) {
                return {
                    success: false,
                    data: "",
                    error: `La impresora tiene una transacción previa abierta (STS1=${this._formatSts(sts1Before)}). Reiníciala y vuelve a intentarlo.`
                };
            }
        }

        try {
            const commands = [];

            // Formato de números según flag 21 (default: "00" = estándar)
            const FLAG21_CONFIGS = {
                "00": { max_amount_int: 8,  max_amount_decimal: 2, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "01": { max_amount_int: 7,  max_amount_decimal: 3, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "02": { max_amount_int: 6,  max_amount_decimal: 4, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "30": { max_amount_int: 14, max_amount_decimal: 2, max_qty_int: 14, max_qty_decimal: 3, max_payment_amount_int: 15, max_payment_amount_decimal: 2, disc_int: 15, disc_decimal: 2 },
            };
            const flag21Key = String(orderData.flag_21 || "00");
            const config = flag21Config || FLAG21_CONFIGS[flag21Key] || FLAG21_CONFIGS["00"];

            // 1. RIF del cliente
            const vat = orderData.partner?.vat || "V00000000";
            commands.push(`iR*${vat}`);

            // 2. Razón social del cliente
            const name = (orderData.partner?.name || "CLIENTE GENERICO").substring(0, 127);
            commands.push(`iS*${name}`);

            // 3. Información adicional del encabezado (dirección, teléfono, encabezado POS)
            this._appendHeaderInfo(commands, orderData);

            // 4. Items de la orden
            // Estrategia A: el descuento global ya viene prorrateado en
            // `price_unit` de cada línea positiva. No se emite `q-` aquí.
            for (const line of orderData.lines || []) {
                const linePrice = Number(line.price_unit || 0);
                if (linePrice <= 0) continue;

                const taxChar = this._getTaxCharacter(line.fiscal_code || "1");
                const price = this._formatAmount(linePrice, config.max_amount_int, config.max_amount_decimal);
                const qty   = this._formatAmount(line.quantity || 1, config.max_qty_int, config.max_qty_decimal);
                const code  = line.product_code ? `|${line.product_code}|` : "";
                const desc  = (line.product_name || "PRODUCTO")
                    .substring(0, 127)
                    .replace(/Ñ/g, 'N')
                    .replace(/ñ/g, 'n')
                    .trim();

                commands.push(`${taxChar}${price}${qty}${code}${desc}`);
            }

            // 5. Subtotal
            commands.push("3");

            // 6. Pagos y cierre fiscal (1XX/2XX + 101)
            this._appendPaymentCommands(commands, orderData, config);

            // 7. Líneas al pie (footer de POS + operador/pedido)
            this._appendFooterInfo(commands, orderData);

            // 8. Fin de documento
            commands.push("199");

            for (let i = 0; i < commands.length; i++) {
                const cmd = commands[i];
                const isFirst = i === 0;
                const result = await this.sendCommand(cmd, null, false, !isFirst);

                const is1xx = cmd.length === 3 && cmd.startsWith("1");
                if (!result.success) {
                    if (is1xx) {
                        console.warn("TfhkaDriver:: Comando 1XX falló (no fatal):", cmd, result.error);
                        continue;
                    }
                    console.error("TfhkaDriver:: Comando falló:", cmd, result.error);
                    await this.abortTransaction();
                    return {
                        success: false,
                        data: "",
                        error: `Error en comando [${cmd}]: ${result.error}`
                    };
                }
            }

            const s1Result = await this._readS1Data();
            if (!s1Result.success) {
                return {
                    success: false,
                    data: "",
                    error: `Factura impresa, pero no se pudo leer S1: ${s1Result.error}`,
                };
            }

            const invoiceNumber = s1Result.data.lastInvoiceNumber;
            if (!invoiceNumber) {
                return {
                    success: false,
                    data: "",
                    error: "Factura impresa, pero S1 no devolvió número de factura",
                };
            }

            const fiscalResponse = this._buildFiscalResponse(
                "Factura impresa correctamente",
                invoiceNumber,
                s1Result.data
            );
            fiscalResponse.global_discount_amount = Number(orderData?.global_discount_amount || 0);
            fiscalResponse.global_discount_rate = Number(orderData?.global_discount_rate || 0);
            fiscalResponse.global_clamped = Boolean(orderData?.global_clamped);
            if (fiscalResponse.global_clamped) {
                console.warn(
                    "TfhkaDriver:: Descuento global clampeado a 100%. Monto POS:",
                    fiscalResponse.global_discount_amount,
                    "Tasa aplicada:",
                    fiscalResponse.global_discount_rate
                );
            }
            return fiscalResponse;

        } catch (error) {
            console.error("TfhkaDriver:: Error al imprimir factura", error);
            await this.abortTransaction();
            return { success: false, data: "", error: error.message };
        }
    }

    /**
     * Imprime una nota de crédito fiscal (devolución/NC)
     * 
     * Diferencias con factura:
     * - Items usan prefijo "d" + código_fiscal_numérico (no "!" / '"' / "#")
     * - Requiere datos de la factura afectada: número, fecha, serial MF
     * 
     * @param {Object} orderData - Datos de la orden
     * @returns {Promise<Object>}
     */
    async printCreditNote(orderData) {
        if (!this.isConnected) {
            return { success: false, data: "", error: "Impresora no conectada" };
        }

        // Validar que tenga factura afectada
        const affected = orderData.invoice_affected;
        if (!affected?.number) {
            return { success: false, data: "", error: "Nota de crédito requiere número de factura afectada" };
        }
        if (!affected?.date) {
            return { success: false, data: "", error: "Nota de crédito requiere fecha de factura afectada" };
        }
        if (!affected?.serial_machine) {
            return { success: false, data: "", error: "Nota de crédito requiere serial de máquina fiscal de la factura afectada" };
        }

        // Verificar estado de la impresora
        const statusBefore = await this.getStatus();
        if (!statusBefore) {
            return { success: false, data: "", error: "No se puede leer el estado de la impresora" };
        }
        const sts1 = statusBefore.raw?.sts1;
        if (!this._isWaitingState(sts1)) {
            const aborted = await this.abortTransaction();
            if (!aborted) {
                return {
                    success: false,
                    data: "",
                    error: `La impresora tiene una transacción previa abierta (STS1=${this._formatSts(sts1)}). Reiníciala.`,
                };
            }
        }

        try {
            const commands = [];

            const FLAG21_CONFIGS = {
                "00": { max_amount_int: 8,  max_amount_decimal: 2, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "01": { max_amount_int: 7,  max_amount_decimal: 3, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "02": { max_amount_int: 6,  max_amount_decimal: 4, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "30": { max_amount_int: 14, max_amount_decimal: 2, max_qty_int: 14, max_qty_decimal: 3, max_payment_amount_int: 15, max_payment_amount_decimal: 2, disc_int: 15, disc_decimal: 2 },
            };
            const config = FLAG21_CONFIGS[String(orderData.flag_21 || "00")] || FLAG21_CONFIGS["00"];

            // 1. RIF del cliente
            const vat = orderData.partner?.vat || "V00000000";
            commands.push(`iR*${vat}`);

            // 2. Razón social del cliente
            const name = (orderData.partner?.name || "CLIENTE GENERICO").substring(0, 127);
            commands.push(`iS*${name}`);

            // 3. Número de factura afectada (8 dígitos con cero a la izquierda)
            const invoiceNumber = String(affected.number).padStart(8, '0');
            commands.push(`iF*${invoiceNumber}`);

            // 4. Serial de la máquina fiscal de la factura afectada
            commands.push(`iI*${affected.serial_machine}`);

            // 5. Fecha de factura afectada (formato DD/MM/YYYY)
            commands.push(`iD*${affected.date}`);

            // 6. Información adicional del encabezado (dirección, teléfono, encabezado POS)
            this._appendHeaderInfo(commands, orderData);

            // 8. Items de la devolución
            // NC usa "d" + código_fiscal_numérico + precio + qty + desc
            let globalDiscountAmount = Math.abs(Number(orderData.global_discount_amount || 0));
            for (const line of orderData.lines || []) {
                const linePrice = Number(line.price_unit || 0);
                if (linePrice < 0) {
                    globalDiscountAmount += Math.abs(linePrice);
                    continue;
                }
                if (linePrice <= 0) continue;

                const fiscalCode = String(line.fiscal_code || "1");
                const price = this._formatAmount(linePrice, config.max_amount_int, config.max_amount_decimal);
                const qty   = this._formatAmount(line.quantity || 1, config.max_qty_int, config.max_qty_decimal);
                const code  = line.product_code ? `|${line.product_code}|` : "";
                const desc  = (line.product_name || "PRODUCTO")
                    .substring(0, 127)
                    .replace(/Ñ/g, 'N').replace(/ñ/g, 'n')
                    .trim();

                // NC: prefijo "d" + código fiscal numérico (no carácter especial)
                commands.push(`d${fiscalCode}${price}${qty}${code}${desc}`);
            }

            // 9. Subtotal
            commands.push("3");

            // 9.1 Descuento global absoluto (q-)
            if (globalDiscountAmount > 0) {
                const discount = this._formatAmount(globalDiscountAmount, config.disc_int, config.disc_decimal);
                commands.push(`q-${discount}`);
            }

            // 10. Pagos y cierre fiscal (1XX/2XX + 101)
            this._appendPaymentCommands(commands, orderData, config);

            // 11. Líneas al pie (footer de POS + operador/pedido)
            this._appendFooterInfo(commands, orderData);

            // 12. Fin de documento
            commands.push("199");

            for (let i = 0; i < commands.length; i++) {
                const cmd = commands[i];
                const result = await this.sendCommand(cmd, null, false, i > 0);
                const is1xx = cmd.length === 3 && cmd.startsWith("1");
                if (!result.success) {
                    if (is1xx) {
                        console.warn("TfhkaDriver:: NC - Comando 1XX falló (no fatal):", cmd, result.error);
                        continue;
                    }
                    console.error("TfhkaDriver:: NC - Comando falló:", cmd, result.error);
                    await this.abortTransaction();
                    return { success: false, data: "", error: `Error en comando [${cmd}]: ${result.error}` };
                }
            }

            const s1Result = await this._readS1Data();
            if (!s1Result.success) {
                return {
                    success: false,
                    data: "",
                    error: `Nota de crédito impresa, pero no se pudo leer S1: ${s1Result.error}`,
                };
            }

            const creditNoteNumber = s1Result.data.lastNCNumber;
            if (!creditNoteNumber) {
                return {
                    success: false,
                    data: "",
                    error: "Nota de crédito impresa, pero S1 no devolvió número de NC",
                };
            }

            return this._buildFiscalResponse("Nota de crédito impresa correctamente", creditNoteNumber, s1Result.data);

        } catch (error) {
            console.error("TfhkaDriver:: Error al imprimir nota de crédito", error);
            await this.abortTransaction();
            return { success: false, data: "", error: error.message };
        }
    }

    /**
     * Imprime una nota de débito fiscal (ND)
     * 
     * Diferencias con factura:
     * - Items usan prefijo backtick (`) + código_fiscal_texto + precio + qty + desc
     * - Requiere datos de la factura afectada: número, fecha, serial MF
     * 
     * @param {Object} orderData - Datos de la orden
     * @returns {Promise<Object>}
     */
    async printDebitNote(orderData) {
        if (!this.isConnected) {
            return { success: false, data: "", error: "Impresora no conectada" };
        }

        // Validar factura afectada
        const affected = orderData.invoice_affected;
        if (!affected?.number) {
            return { success: false, data: "", error: "Nota de débito requiere número de factura afectada" };
        }
        if (!affected?.date) {
            return { success: false, data: "", error: "Nota de débito requiere fecha de factura afectada" };
        }
        if (!affected?.serial_machine) {
            return { success: false, data: "", error: "Nota de débito requiere serial de máquina fiscal de la factura afectada" };
        }

        // Verificar estado de la impresora
        const statusBefore = await this.getStatus();
        if (!statusBefore) {
            return { success: false, data: "", error: "No se puede leer el estado de la impresora" };
        }
        const sts1 = statusBefore.raw?.sts1;
        if (!this._isWaitingState(sts1)) {
            const aborted = await this.abortTransaction();
            if (!aborted) {
                return {
                    success: false,
                    data: "",
                    error: `La impresora tiene una transacción previa abierta (STS1=${this._formatSts(sts1)}). Reiníciala.`,
                };
            }
        }

        try {
            const commands = [];

            const FLAG21_CONFIGS = {
                "00": { max_amount_int: 8,  max_amount_decimal: 2, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "01": { max_amount_int: 7,  max_amount_decimal: 3, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "02": { max_amount_int: 6,  max_amount_decimal: 4, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "30": { max_amount_int: 14, max_amount_decimal: 2, max_qty_int: 14, max_qty_decimal: 3, max_payment_amount_int: 15, max_payment_amount_decimal: 2, disc_int: 15, disc_decimal: 2 },
            };
            const config = FLAG21_CONFIGS[String(orderData.flag_21 || "00")] || FLAG21_CONFIGS["00"];

            // 1. RIF del cliente (ND: va primero, antes de la factura afectada)
            const vat = orderData.partner?.vat || "V00000000";
            commands.push(`iR*${vat}`);

            // 2. Razón social del cliente
            const name = (orderData.partner?.name || "CLIENTE GENERICO").substring(0, 127);
            commands.push(`iS*${name}`);

            // 3. Número de factura afectada
            const invoiceNumber = String(affected.number).padStart(8, '0');
            commands.push(`iF*${invoiceNumber}`);

            // 4. Serial de la máquina fiscal afectada
            commands.push(`iI*${affected.serial_machine}`);

            // 5. Fecha de factura afectada
            commands.push(`iD*${affected.date}`);

            // 6. Información adicional del encabezado (dirección, teléfono, encabezado POS)
            this._appendHeaderInfo(commands, orderData);

            // 8. Items de la nota de débito
            // ND usa backtick (`) + código_fiscal_texto + precio + qty + desc
            let globalDiscountAmount = Math.abs(Number(orderData.global_discount_amount || 0));
            for (const line of orderData.lines || []) {
                const linePrice = Number(line.price_unit || 0);
                if (linePrice < 0) {
                    globalDiscountAmount += Math.abs(linePrice);
                    continue;
                }
                if (linePrice <= 0) continue;

                const fiscalCode = String(line.fiscal_code || "1");
                const price = this._formatAmount(linePrice, config.max_amount_int, config.max_amount_decimal);
                const qty   = this._formatAmount(line.quantity || 1, config.max_qty_int, config.max_qty_decimal);
                const code  = line.product_code ? `|${line.product_code}|` : "";
                const desc  = (line.product_name || "PRODUCTO")
                    .substring(0, 127)
                    .replace(/Ñ/g, 'N').replace(/ñ/g, 'n')
                    .trim();

                // ND: backtick + código fiscal texto + precio + qty + desc
                commands.push(`\`${fiscalCode}${price}${qty}${code}${desc}`);
            }

            // 9. Subtotal
            commands.push("3");

            // 9.1 Descuento global absoluto (q-)
            if (globalDiscountAmount > 0) {
                const discount = this._formatAmount(globalDiscountAmount, config.disc_int, config.disc_decimal);
                commands.push(`q-${discount}`);
            }

            // 10. Pagos y cierre fiscal (1XX/2XX + 101)
            this._appendPaymentCommands(commands, orderData, config);

            // 11. Líneas al pie (footer de POS + operador/pedido)
            this._appendFooterInfo(commands, orderData);

            // 12. Fin de documento
            commands.push("199");

            for (let i = 0; i < commands.length; i++) {
                const cmd = commands[i];
                const result = await this.sendCommand(cmd, null, false, i > 0);
                const is1xx = cmd.length === 3 && cmd.startsWith("1");
                if (!result.success) {
                    if (is1xx) {
                        console.warn("TfhkaDriver:: ND - Comando 1XX falló (no fatal):", cmd, result.error);
                        continue;
                    }
                    console.error("TfhkaDriver:: ND - Comando falló:", cmd, result.error);
                    await this.abortTransaction();
                    return { success: false, data: "", error: `Error en comando [${cmd}]: ${result.error}` };
                }
            }

            const s1Result = await this._readS1Data();
            if (!s1Result.success) {
                return {
                    success: false,
                    data: "",
                    error: `Nota de débito impresa, pero no se pudo leer S1: ${s1Result.error}`,
                };
            }

            const debitNoteNumber = s1Result.data.lastDebtNoteNumber;
            if (!debitNoteNumber) {
                return {
                    success: false,
                    data: "",
                    error: "Nota de débito impresa, pero S1 no devolvió número de ND",
                };
            }

            return this._buildFiscalResponse("Nota de débito impresa correctamente", debitNoteNumber, s1Result.data);

        } catch (error) {
            console.error("TfhkaDriver:: Error al imprimir nota de débito", error);
            await this.abortTransaction();
            return { success: false, data: "", error: error.message };
        }
    }
}
