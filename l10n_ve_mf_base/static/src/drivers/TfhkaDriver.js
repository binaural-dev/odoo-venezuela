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
    
    // Máximo de caracteres por línea que imprime la TFHKA
    static MAX_LINE_LEN = 40;

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
     * Divide un texto en líneas de máximo maxLen caracteres,
     * respetando límites de palabra cuando sea posible.
     * @param {string} text - texto a dividir
     * @param {number} maxLen - caracteres máximos por línea
     * @returns {string[]} - array de líneas
     */
    _wordWrap(text, maxLen) {
        if (!text) return [""];
        if (text.length <= maxLen) return [text];
        const lines = [];
        const words = text.split(" ");
        let current = "";
        for (const word of words) {
            const candidate = current ? current + " " + word : word;
            if (candidate.length > maxLen) {
                if (current) lines.push(current);
                // Si la palabra sola excede maxLen, partir por caracteres
                if (word.length > maxLen) {
                    for (let i = 0; i < word.length; i += maxLen) {
                        lines.push(word.substring(i, i + maxLen));
                    }
                } else {
                    current = word;
                }
            } else {
                current = candidate;
            }
        }
        if (current) lines.push(current);
        return lines;
    }

    /**
     * Conecta con la impresora fiscal
     * @returns {Promise<boolean>}
     */
    async connect({ requestPermission = false } = {}) {
        try {
            // Intentar reconexión automática primero
            let connected = await this.connection.autoConnect();
            
            // Solo solicitar permiso si se indica explícitamente
            // (requestPort() requiere un gesto del usuario)
            if (!connected && requestPermission) {
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
                    if (command === "199") {
                        console.log("TfhkaDriver::sendCommand - 199 ACK (cierre aceptado)");
                    }
                    return { success: true, data: "ACK", error: "" };
                }

                if (FiscalProtocol.isNAK(response)) {
                    if (command === "199") {
                        console.error("TfhkaDriver::sendCommand - 199 NAK: la impresora rechazó el cierre. Los montos 2XX no coinciden con subtotal+IVA+IGTF calculado por la impresora.");
                    } else {
                        console.warn(`TfhkaDriver:: NAK recibido para [${command}], reintentando...`);
                    }
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
     * Consulta país y modelo de la máquina fiscal (comando SV).
     *
     * Respuesta típica: "SVZ1FVE" → modelCode="Z1F" (SRP-812), country="VE".
     *
     * @returns {Promise<Object>} - { success, data: { modelCode, model, country, raw }, error }
     */
    async getMachineModel() {
        if (!this.isConnected) {
            return { success: false, data: null, error: "Impresora no conectada" };
        }

        const response = await this.sendCommand("SV", 5000, false);
        if (!response.success) {
            return { success: false, data: null, error: response.error || "No se pudo leer SV" };
        }

        const payload = String(response.data || "")
            .replace(/^\u0002/, "")
            .replace(/\u0003$/, "")
            .replace(/^SV/, "")
            .trim();

        if (!payload || payload.length < 3) {
            return {
                success: false,
                data: null,
                error: "Respuesta SV inválida de la impresora",
            };
        }

        const country = payload.slice(-2);
        const modelCode = payload.slice(0, -2);
        const MODEL_MAP = {
            Z1F: "SRP-812",
        };

        return {
            success: true,
            data: {
                modelCode,
                model: MODEL_MAP[modelCode] || modelCode,
                country,
                raw: payload,
            },
            error: "",
        };
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


    // ========== UTILIDADES PRIVADAS ==========


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

    /**
     * Parsea la respuesta del comando S25 (manual IGTF TFHKA v1.1.0, Tabla 10).
     * S25 informa el desglose IGTF del documento fiscal EN CURSO (factura,
     * NC o ND abierta). Si no hay documento abierto, los valores vienen en 0.
     *
     * Campos (en orden, separados por 0x0A al igual que S1/S3):
     *   1. Subtotal de bases imponibles
     *   2. Subtotal de Impuesto
     *   3. Monto a Pagar Incluyendo IGTF
     *   4. Cantidad de Artículos
     *   5. Monto a Pagar (sin IGTF)
     *   6. Cantidad de pagos realizados
     *   7. Tipo de Documento (0=Ninguno, 1=Factura, 2=NC, 3=ND)
     *
     * El monto de IGTF se calcula como la diferencia entre "Monto a Pagar
     * Incluyendo IGTF" y "Monto a Pagar".
     * @param {string} rawData
     * @returns {Object|null}
     */
    _parseS25Data(rawData) {
        if (!rawData) {
            return null;
        }

        const payload = String(rawData)
            .replace(/^\u0002/, "")
            .replace(/\u0003$/, "")
            .replace(/^S2/, "");

        const fields = payload
            .split("\n")
            .map((value) => value.replace(/\r/g, "").trim())
            .filter((value) => value.length > 0);

        if (fields.length < 6) {
            return null;
        }

        const documentTypeLabels = {
            "0": "Ninguno",
            "1": "Factura",
            "2": "Nota de Crédito",
            "3": "Nota de Débito",
        };

        const subtotalBases = this._decodeImplicit2Decimals(fields[0]);
        const subtotalTax = this._decodeImplicit2Decimals(fields[1]);
        const totalWithIgtf = this._decodeImplicit2Decimals(fields[2]);
        const itemCount = parseInt(fields[3], 10) || 0;
        const totalWithoutIgtf = this._decodeImplicit2Decimals(fields[4]);
        const paymentCount = parseInt(fields[5], 10) || 0;
        const documentTypeCode = fields[6] !== undefined ? String(fields[6]).trim() : "";
        const igtfAmount = Number((totalWithIgtf - totalWithoutIgtf).toFixed(2));

        return {
            subtotalBases,
            subtotalTax,
            totalWithIgtf,
            totalWithoutIgtf,
            igtfAmount,
            itemCount,
            paymentCount,
            documentType: documentTypeCode,
            documentTypeLabel: documentTypeLabels[documentTypeCode] || "Desconocido",
            raw: fields,
        };
    }

    /**
     * Lee el status S25 (desglose IGTF del documento fiscal en curso).
     * Solo tiene datos significativos si hay una transacción fiscal abierta
     * (factura/NC/ND iniciada). Fuera de una transacción retorna ceros.
     * @returns {Promise<Object>} - { success, data, error }
     */
    async readS25Data() {
        const response = await this.sendCommand("S25", 5000, false);
        if (!response.success) {
            return { success: false, data: null, error: response.error || "No se pudo leer S25" };
        }

        const data = this._parseS25Data(response.data);
        if (!data) {
            return {
                success: false,
                data: null,
                error: "No se pudo parsear la respuesta S25 de la impresora",
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

    _appendHeaderInfo(commands, orderData, startIndex = 0) {
        let infoIndex = startIndex;

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

        return infoIndex;
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

    /**
     * Formatea un monto para mostrar en líneas informativas del ticket
     * (NO usar para comandos de protocolo tipo 2XX, esos usan _formatAmount
     * con dígitos crudos). Formato venezolano: punto para miles, coma para
     * decimales. Ej: 39290.94 -> "39.290,94"
     * @param {number} value
     * @returns {string}
     */
    _formatDisplayAmount(value) {
        const [intPart, decPart] = Number(value).toFixed(2).split(".");
        const intWithThousands = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        return `${intWithThousands},${decPart}`;
    }

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

        const amountStr = this._formatDisplayAmount(amount);
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

    /**
     * Determina si un código de método de pago corresponde a un medio en
     * DIVISAS según el manual IGTF de TFHKA (v1.1.0, sección 7):
     *   - 01 a 19: PAGO EN MONEDA NACIONAL (no aplica IGTF)
     *   - 20 a 24: PAGO EN DIVISAS (aplica IGTF si Flag 50 = 01)
     * @param {string|number} methodCode
     * @returns {boolean}
     */
    _isDivisaPaymentMethod(methodCode) {
        const code = parseInt(String(methodCode).replace(/[^0-9]/g, ""), 10);
        return Number.isInteger(code) && code >= 20 && code <= 24;
    }

    /**
     * Determina si el conjunto de pagos de la orden contiene al menos un
     * medio de pago en divisas (códigos 20-24). Si es así, el cierre fiscal
     * DEBE usar el comando "199" (obligatorio con Flag 50=01) en vez del
     * cierre directo "1XX", según el manual IGTF de TFHKA.
     * @param {Array} payments - orderData.payment_lines
     * @returns {boolean}
     */
    _hasDivisaPayment(payments) {
        return (payments || []).some((payment) =>
            this._isDivisaPaymentMethod(payment.payment_method_code)
        );
    }

    _appendPaymentCommands(commands, orderData, config) {
        const payments = orderData.payment_lines || [];

        console.log("TfhkaDriver::PaymentCommands - payment_lines recibidos:", JSON.stringify(payments));
        const totalPayments = payments.reduce((sum, p) => sum + Math.abs(Number(p.amount || 0)), 0);
        console.log("TfhkaDriver::PaymentCommands - suma total de pagos:", totalPayments);

        if (orderData.has_cashbox) {
            commands.push("w");
        }

        const hasDivisa = this._hasDivisaPayment(payments);
        console.log("TfhkaDriver::PaymentCommands - hasDivisa:", hasDivisa,
            "codigos:", (payments || []).map(p => p.payment_method_code));

        if (!payments.length) {
            commands.push("101");
            return;
        }

        // IGTF (manual TFHKA v1.1.0): si hay pago en divisas (20-24), el
        // cierre NO puede ser "1XX" — se deben enviar TODOS los métodos
        // como "2XX" (incluido el que normalmente cerraría) y dejar que el
        // comando "199" final (ya emitido al final de cada documento fiscal
        // en printInvoice/printCreditNote/printDebitNote) haga el cierre.
        //
        // IMPORTANTE (ver manual impuesto_igtf.md, seccion 7, punto 5): el
        // comando "199" SOLO es aceptado por la impresora si el documento
        // fue pagado en su totalidad (según el cálculo interno de LA
        // IMPRESORA, que incluye su propio cálculo de IGTF sobre el monto en
        // divisas). Si la suma de los montos 2XX enviados no coincide
        // exactamente con lo que la impresora espera (subtotal + IVA + IGTF
        // calculado por ELLA), rechaza el "199" con NAK y el documento no se
        // cierra (no se corta el papel).
        //
        // NO se agrupan los pagos por método aquí: el IGTF se calcula por
        // cada pago en divisa que la impresora recibe individualmente. Si
        // hay 2 pagos con el mismo método en divisa, deben enviarse como 2
        // comandos "2XX" separados (no sumados en uno solo), para que el
        // cálculo de IGTF de la impresora sea fiel a cómo se recibieron los
        // pagos realmente.
        if (hasDivisa) {
            for (const payment of payments) {
                const amount = Math.abs(Number(payment.amount || 0));
                if (amount <= 0) {
                    continue;
                }
                const methodCode = String(payment.payment_method_code || "01").padStart(2, '0');
                const amountStr = this._formatAmount(
                    amount,
                    config.max_payment_amount_int,
                    config.max_payment_amount_decimal
                );
                const paymentCmd = `2${methodCode}${amountStr}`;
                console.log("TfhkaDriver::PaymentCommands - enviando pago:", {
                    metodo: methodCode,
                    monto: amount,
                    cmd: paymentCmd
                });
                commands.push(paymentCmd);
            }
            console.log("TfhkaDriver::PaymentCommands - total comandos 2XX:", (commands || []).filter(c => c.startsWith("2")).length);
            // NO se envía "1XX": el "199" final cierra el documento con IGTF.
            return;
        }

        // Sin divisas: se puede agrupar por método de pago con seguridad,
        // ya que no hay cálculo de IGTF involucrado.
        const groupedPayments = {};
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
     * Ajusta los montos de pago en divisa para incluir el IGTF calculado
     * por la impresora (leído vía S25). Suma el IGTF al primer pago cuyo
     * código de método esté en el rango 20-24.
     *
     * @param {Array} paymentLines - payment_lines originales
     * @param {Object} s25Data - datos del S25 (con igtfAmount)
     * @returns {Array} - payment_lines ajustados
     */
    _adjustPaymentsWithIGTF(paymentLines, s25Data) {
        const igtfAmount = Number(s25Data?.igtfAmount || 0);
        if (igtfAmount <= 0) {
            return paymentLines;
        }

        const adjusted = paymentLines.map(p => ({ ...p }));
        for (const line of adjusted) {
            if (this._isDivisaPaymentMethod(line.payment_method_code)) {
                const original = line.amount;
                line.amount = Number((line.amount + igtfAmount).toFixed(2));
                console.log("TfhkaDriver:: Ajustando pago divisa con IGTF:", {
                    codigo: line.payment_method_code,
                    monto_original: original,
                    igtf: igtfAmount,
                    monto_ajustado: line.amount,
                });
                break;
            }
        }
        return adjusted;
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
            // Formato de números según flag 21 (default: "00" = estándar)
            const FLAG21_CONFIGS = {
                "00": { max_amount_int: 8,  max_amount_decimal: 2, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "01": { max_amount_int: 7,  max_amount_decimal: 3, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "02": { max_amount_int: 6,  max_amount_decimal: 4, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "30": { max_amount_int: 14, max_amount_decimal: 2, max_qty_int: 14, max_qty_decimal: 3, max_payment_amount_int: 15, max_payment_amount_decimal: 2, disc_int: 15, disc_decimal: 2 },
            };
            const flag21Key = String(orderData.flag_21 || "00");
            const config = flag21Config || FLAG21_CONFIGS[flag21Key] || FLAG21_CONFIGS["00"];

            // ================================================================
            // FASE 1: Construir y enviar comandos de apertura (RIF, nombre,
            // encabezado, items, subtotal)
            // ================================================================
            const phase1Commands = [];

            // 1. RIF del cliente
            const vat = orderData.partner?.vat || "V00000000";
            phase1Commands.push(`iR*${vat}`);

            // 2. Razón social del cliente (word-wrap: primera línea como iS*,
            // continuaciones como informativas iNN ANTES del header)
            const nameLines = this._wordWrap(
                orderData.partner?.name || "CLIENTE GENERICO",
                TfhkaDriver.MAX_LINE_LEN
            );
            phase1Commands.push(`iS*${nameLines[0]}`);
            let nameInfoCount = 0;
            const MAX_INFO_LINES = 10;
            for (let i = 1; i < nameLines.length && nameInfoCount < MAX_INFO_LINES; i++) {
                phase1Commands.push(`i${String(nameInfoCount++).padStart(2, '0')}${nameLines[i]}`);
            }

            // 3. Información adicional del encabezado (continúa después de las
            // líneas del nombre)
            this._appendHeaderInfo(phase1Commands, orderData, nameInfoCount);

            // 5. Items de la orden (truncado simple — el protocolo no permite
            // continuar items en líneas informativas iNN)
            for (const line of orderData.lines || []) {
                const linePrice = Number(line.price_unit || 0);
                if (linePrice <= 0) continue;

                const taxChar = this._getTaxCharacter(line.fiscal_code || "1");
                const price = this._formatAmount(linePrice, config.max_amount_int, config.max_amount_decimal);
                const qty   = this._formatAmount(line.quantity || 1, config.max_qty_int, config.max_qty_decimal);
                const code  = line.product_code ? `|${line.product_code}|` : "";
                let desc  = (line.product_name || "PRODUCTO")
                    .replace(/Ñ/g, 'N')
                    .replace(/ñ/g, 'n')
                    .trim();

                const overhead = 1 + price.length + qty.length + code.length;
                const available = TfhkaDriver.MAX_LINE_LEN - overhead;
                if (available > 0 && desc.length > available) {
                    desc = desc.substring(0, available);
                }

                phase1Commands.push(`${taxChar}${price}${qty}${code}${desc}`);
            }

            // 7. Subtotal
            phase1Commands.push("3");
            console.log("TfhkaDriver::printInvoice - FASE 1: items:", orderData.lines?.length, "comandos:", phase1Commands.length);

            // Enviar FASE 1 a la impresora
            for (let i = 0; i < phase1Commands.length; i++) {
                const result = await this.sendCommand(phase1Commands[i], null, false, i > 0);
                if (!result.success) {
                    console.error("TfhkaDriver:: FASE 1 - comando falló:", phase1Commands[i], result.error);
                    await this.abortTransaction();
                    return { success: false, data: "", error: `Error en comando FASE 1 [${phase1Commands[i]}]: ${result.error}` };
                }
            }

            // ================================================================
            // FASE 1.5: Leer S25 para obtener IGTF si hay pagos en divisa
            // ================================================================
            let paymentLines = orderData.payment_lines || [];
            const hasDivisa = this._hasDivisaPayment(paymentLines);
            console.log("TfhkaDriver::printInvoice - hasDivisa:", hasDivisa, "payment_lines originales:", JSON.stringify(paymentLines));

            if (hasDivisa) {
                const s25Result = await this.readS25Data();
                console.log("TfhkaDriver::printInvoice - S25 result:", s25Result);
                if (s25Result.success && s25Result.data) {
                    console.log("TfhkaDriver::printInvoice - S25 data:", JSON.stringify(s25Result.data));
                } else {
                    console.warn("TfhkaDriver::printInvoice - No se pudo leer S25, continuando sin ajuste IGTF:", s25Result.error);
                }
            }

            // ================================================================
            // FASE 2: Construir y enviar pagos + footer + cierre
            // ================================================================
            const phase2Commands = [];
            this._appendPaymentCommands(phase2Commands, { ...orderData, payment_lines: paymentLines }, config);
            this._appendFooterInfo(phase2Commands, orderData);
            phase2Commands.push("199");

            let payment199Result = null;
            for (let i = 0; i < phase2Commands.length; i++) {
                const cmd = phase2Commands[i];
                const result = await this.sendCommand(cmd, null, false, true);

                if (cmd === "199") {
                    payment199Result = result;
                }

                const is1xx = cmd.length === 3 && cmd.startsWith("1");
                if (!result.success) {
                    if (is1xx) {
                        console.warn("TfhkaDriver:: Comando 1XX falló (no fatal):", cmd, result.error);
                        continue;
                    }
                    if (cmd === "199") {
                        console.error("TfhkaDriver:: Comando 199 falló (NAK) — la impresora rechazó el cierre. Montos 2XX no coinciden con su cálculo interno (subtotal+IVA+IGTF).");
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

            console.log("TfhkaDriver::printInvoice - resultado del 199:", payment199Result);

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
            const FLAG21_CONFIGS = {
                "00": { max_amount_int: 8,  max_amount_decimal: 2, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "01": { max_amount_int: 7,  max_amount_decimal: 3, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "02": { max_amount_int: 6,  max_amount_decimal: 4, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "30": { max_amount_int: 14, max_amount_decimal: 2, max_qty_int: 14, max_qty_decimal: 3, max_payment_amount_int: 15, max_payment_amount_decimal: 2, disc_int: 15, disc_decimal: 2 },
            };
            const config = FLAG21_CONFIGS[String(orderData.flag_21 || "00")] || FLAG21_CONFIGS["00"];

            // ================================================================
            // FASE 1: Construir y enviar comandos de apertura
            // ================================================================
            const phase1Commands = [];

            // 1. RIF del cliente
            const vat = orderData.partner?.vat || "V00000000";
            phase1Commands.push(`iR*${vat}`);

            // 2. Razón social del cliente
            const nameLines = this._wordWrap(
                orderData.partner?.name || "CLIENTE GENERICO",
                TfhkaDriver.MAX_LINE_LEN
            );
            phase1Commands.push(`iS*${nameLines[0]}`);
            let nameInfoCount = 0;
            const MAX_INFO_LINES = 10;
            for (let i = 1; i < nameLines.length && nameInfoCount < MAX_INFO_LINES; i++) {
                phase1Commands.push(`i${String(nameInfoCount++).padStart(2, '0')}${nameLines[i]}`);
            }

            // 3. Número de factura afectada
            const invoiceNumber = String(affected.number).padStart(8, '0');
            phase1Commands.push(`iF*${invoiceNumber}`);

            // 4. Serial de la máquina fiscal
            phase1Commands.push(`iI*${affected.serial_machine}`);

            // 5. Fecha de factura afectada
            phase1Commands.push(`iD*${affected.date}`);

            // 6. Encabezado
            this._appendHeaderInfo(phase1Commands, orderData, nameInfoCount);

            // 8. Items de la devolución ("d" + código_fiscal + precio + qty + desc)
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
                let desc  = (line.product_name || "PRODUCTO")
                    .replace(/Ñ/g, 'N').replace(/ñ/g, 'n')
                    .trim();

                const overhead = 2 + price.length + qty.length + code.length;
                const available = TfhkaDriver.MAX_LINE_LEN - overhead;
                if (available > 0 && desc.length > available) {
                    desc = desc.substring(0, available);
                }

                phase1Commands.push(`d${fiscalCode}${price}${qty}${code}${desc}`);
            }

            // 9. Subtotal
            phase1Commands.push("3");

            // 9.1 Descuento global
            if (globalDiscountAmount > 0) {
                const discount = this._formatAmount(globalDiscountAmount, config.disc_int, config.disc_decimal);
                phase1Commands.push(`q-${discount}`);
            }

            // Enviar FASE 1
            for (let i = 0; i < phase1Commands.length; i++) {
                const result = await this.sendCommand(phase1Commands[i], null, false, i > 0);
                if (!result.success) {
                    console.error("TfhkaDriver:: NC FASE 1 - comando falló:", phase1Commands[i], result.error);
                    await this.abortTransaction();
                    return { success: false, data: "", error: `Error NC [${phase1Commands[i]}]: ${result.error}` };
                }
            }

            // ================================================================
            // FASE 1.5: Leer S25 para IGTF
            // ================================================================
            let paymentLines = orderData.payment_lines || [];
            const hasDivisa = this._hasDivisaPayment(paymentLines);
            if (hasDivisa) {
                const s25Result = await this.readS25Data();
                if (!s25Result.success) {
                    console.warn("TfhkaDriver::printCreditNote - No se pudo leer S25:", s25Result.error);
                }
            }

            // ================================================================
            // FASE 2: Pagos + footer + cierre
            // ================================================================
            const phase2Commands = [];
            this._appendPaymentCommands(phase2Commands, { ...orderData, payment_lines: paymentLines }, config);
            this._appendFooterInfo(phase2Commands, orderData);
            phase2Commands.push("199");

            for (let i = 0; i < phase2Commands.length; i++) {
                const cmd = phase2Commands[i];
                const result = await this.sendCommand(cmd, null, false, true);
                const is1xx = cmd.length === 3 && cmd.startsWith("1");
                if (!result.success) {
                    if (is1xx) {
                        console.warn("TfhkaDriver:: NC - Comando 1XX falló (no fatal):", cmd, result.error);
                        continue;
                    }
                    console.error("TfhkaDriver:: NC - Comando falló:", cmd, result.error);
                    await this.abortTransaction();
                    return { success: false, data: "", error: `Error NC [${cmd}]: ${result.error}` };
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
            const FLAG21_CONFIGS = {
                "00": { max_amount_int: 8,  max_amount_decimal: 2, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "01": { max_amount_int: 7,  max_amount_decimal: 3, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "02": { max_amount_int: 6,  max_amount_decimal: 4, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2, disc_int: 7, disc_decimal: 2 },
                "30": { max_amount_int: 14, max_amount_decimal: 2, max_qty_int: 14, max_qty_decimal: 3, max_payment_amount_int: 15, max_payment_amount_decimal: 2, disc_int: 15, disc_decimal: 2 },
            };
            const config = FLAG21_CONFIGS[String(orderData.flag_21 || "00")] || FLAG21_CONFIGS["00"];

            // ================================================================
            // FASE 1: RIF, razón social, factura afectada, encabezado, items
            // ================================================================
            const phase1Commands = [];

            // 1. RIF del cliente (ND: va primero, antes de la factura afectada)
            const vat = orderData.partner?.vat || "V00000000";
            phase1Commands.push(`iR*${vat}`);

            // 2. Razón social del cliente
            const nameLines = this._wordWrap(
                orderData.partner?.name || "CLIENTE GENERICO",
                TfhkaDriver.MAX_LINE_LEN
            );
            phase1Commands.push(`iS*${nameLines[0]}`);
            let nameInfoCount = 0;
            const MAX_INFO_LINES = 10;
            for (let i = 1; i < nameLines.length && nameInfoCount < MAX_INFO_LINES; i++) {
                phase1Commands.push(`i${String(nameInfoCount++).padStart(2, '0')}${nameLines[i]}`);
            }

            // 3. Número de factura afectada
            const invoiceNumber = String(affected.number).padStart(8, '0');
            phase1Commands.push(`iF*${invoiceNumber}`);

            // 4. Serial de la máquina fiscal afectada
            phase1Commands.push(`iI*${affected.serial_machine}`);

            // 5. Fecha de factura afectada
            phase1Commands.push(`iD*${affected.date}`);

            // 6. Encabezado
            this._appendHeaderInfo(phase1Commands, orderData, nameInfoCount);

            // 8. Items de la nota de débito (backtick + código_fiscal + precio + qty + desc)
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
                let desc  = (line.product_name || "PRODUCTO")
                    .replace(/Ñ/g, 'N').replace(/ñ/g, 'n')
                    .trim();

                const overhead = 2 + price.length + qty.length + code.length;
                const available = TfhkaDriver.MAX_LINE_LEN - overhead;
                if (available > 0 && desc.length > available) {
                    desc = desc.substring(0, available);
                }

                phase1Commands.push(`\`${fiscalCode}${price}${qty}${code}${desc}`);
            }

            // 9. Subtotal
            phase1Commands.push("3");

            // 9.1 Descuento global
            if (globalDiscountAmount > 0) {
                const discount = this._formatAmount(globalDiscountAmount, config.disc_int, config.disc_decimal);
                phase1Commands.push(`q-${discount}`);
            }

            for (let i = 0; i < phase1Commands.length; i++) {
                const result = await this.sendCommand(phase1Commands[i], null, false, i > 0);
                if (!result.success) {
                    console.error("TfhkaDriver:: ND FASE 1 - comando falló:", phase1Commands[i], result.error);
                    await this.abortTransaction();
                    return { success: false, data: "", error: `Error ND [${phase1Commands[i]}]: ${result.error}` };
                }
            }

            // ================================================================
            // FASE 1.5: Leer S25 para IGTF
            // ================================================================
            let paymentLines = orderData.payment_lines || [];
            const hasDivisa = this._hasDivisaPayment(paymentLines);
            if (hasDivisa) {
                const s25Result = await this.readS25Data();
                if (!s25Result.success) {
                    console.warn("TfhkaDriver::printDebitNote - No se pudo leer S25:", s25Result.error);
                }
            }

            // ================================================================
            // FASE 2: Pagos + footer + cierre
            // ================================================================
            const phase2Commands = [];
            this._appendPaymentCommands(phase2Commands, { ...orderData, payment_lines: paymentLines }, config);
            this._appendFooterInfo(phase2Commands, orderData);
            phase2Commands.push("199");

            for (let i = 0; i < phase2Commands.length; i++) {
                const cmd = phase2Commands[i];
                const result = await this.sendCommand(cmd, null, false, true);
                const is1xx = cmd.length === 3 && cmd.startsWith("1");
                if (!result.success) {
                    if (is1xx) {
                        console.warn("TfhkaDriver:: ND - Comando 1XX falló (no fatal):", cmd, result.error);
                        continue;
                    }
                    console.error("TfhkaDriver:: ND - Comando falló:", cmd, result.error);
                    await this.abortTransaction();
                    return { success: false, data: "", error: `Error ND [${cmd}]: ${result.error}` };
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
