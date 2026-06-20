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
     * @returns {Promise<Object>} - { success: boolean, data: string, error: string }
     */
    async sendCommand(command, timeout = null, checkStatus = true) {
        if (!this.isConnected) {
            return { success: false, data: "", error: "Impresora no conectada" };
        }

        // Verificar status de la impresora antes de enviar (excepto para ENQ y 199)
        // Los comandos de control de transacción (9, 199) se saltan la verificación
        const skipStatusCheck = ['9', '199', 'w'].includes(command);
        if (checkStatus && command !== 'ENQ' && !skipStatusCheck) {
            const status = await this.getStatus();
            if (!status) {
                return { success: false, data: "", error: "No se pudo leer el estado de la impresora" };
            }

            // Verificar errores críticos (STS2)
            if (status.errors && status.errors.length > 0) {
                const errorMsg = status.errors.join(', ');
                console.error("TfhkaDriver:: Impresora tiene errores:", errorMsg);
                return { success: false, data: "", error: `Error de impresora: ${errorMsg}` };
            }

            // Verificar que la impresora esté en estado "esperando" (STS1)
            // Equivalente al check del SDK Python: status["code"] not in ["1", "4"]
            // 0x40 = Test mode, waiting (code 1)
            // 0x60 = Fiscal mode, waiting (code 4)
            const sts1 = status.raw?.sts1;
            const isWaiting = (sts1 === 0x40 || sts1 === 0x60);
            const isInTransaction = (sts1 === 0x41 || sts1 === 0x61 || sts1 === 0x65 || sts1 === 0x62 || sts1 === 0x42);

            if (isInTransaction) {
                console.warn("TfhkaDriver:: Impresora tiene transacción abierta (STS1:", sts1?.toString(16), "). Intentando abortar...");
                const aborted = await this.abortTransaction();
                if (!aborted) {
                    return {
                        success: false,
                        data: "",
                        error: `Impresora ocupada (STS1=0x${sts1?.toString(16)}). Transacción previa no pudo ser cancelada. Reinicia la impresora.`
                    };
                }
            } else if (!isWaiting && sts1 !== undefined) {
                console.warn("TfhkaDriver:: Estado inesperado STS1:", sts1?.toString(16), "- continuando de todas formas");
            }
        }

        // Auto-ajustar timeout según el tipo de comando
        if (timeout === null) {
            if (command.startsWith('PJ')) {
                timeout = 60000; // 60s para programación (imprime varias páginas)
            } else if (command.startsWith('I0X') || command.startsWith('I0Z')) {
                timeout = 30000; // 30s para reportes X/Z
            } else {
                timeout = 5000; // 5s para comandos normales
            }
        }

        for (let attempt = 0; attempt < this.retryAttempts; attempt++) {
            try {
                // Limpiar buffer antes de enviar (solo en el primer intento)
                if (attempt === 0) {
                    await this.connection.flushBuffer();
                }
                
                // Construir trama
                const frame = FiscalProtocol.buildFrame(command);
                
                console.log(`TfhkaDriver:: Enviando comando [intento ${attempt + 1}/${this.retryAttempts}]:`, 
                    FiscalProtocol.frameToASCII(frame));
                
                // Enviar
                const sent = await this.connection.write(frame);
                if (!sent) {
                    throw new Error("Error al escribir en puerto serial");
                }

                // Esperar respuesta
                const response = await this.connection.read(timeout);
                if (!response) {
                    throw new Error("No se recibió respuesta de la impresora");
                }

                console.log("TfhkaDriver:: Respuesta recibida:", FiscalProtocol.frameToASCII(response));

                // Verificar si es ACK
                if (FiscalProtocol.isACK(response)) {
                    return { success: true, data: "ACK", error: "" };
                }

                // Verificar si es NAK (reintentar)
                if (FiscalProtocol.isNAK(response)) {
                    console.warn(`TfhkaDriver:: NAK recibido, reintentando...`);
                    await new Promise(resolve => setTimeout(resolve, this.retryDelay));
                    continue;
                }

                // Parsear respuesta normal
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
            console.log("TfhkaDriver:: Intentando abortar transacción colgada...");
            
            await this.connection.flushBuffer();

            // Intentar cancelar el documento actual con "9" (Anular Documento)
            const frame9 = FiscalProtocol.buildFrame("9");
            await this.connection.write(frame9);
            const response9 = await this.connection.read(3000);
            
            if (response9 && FiscalProtocol.isACK(response9)) {
                console.log("TfhkaDriver:: Transacción cancelada con comando 9");
                await new Promise(resolve => setTimeout(resolve, 500));
                return true;
            }

            // Si "9" no funcionó, intentar con "199" (Fin de Documento)
            console.warn("TfhkaDriver:: Comando 9 no respondió, intentando 199...");
            const frame199 = FiscalProtocol.buildFrame("199");
            await this.connection.write(frame199);
            const response199 = await this.connection.read(3000);

            if (response199 && FiscalProtocol.isACK(response199)) {
                console.log("TfhkaDriver:: Transacción cancelada con comando 199");
                await new Promise(resolve => setTimeout(resolve, 500));
                return true;
            }

            // Verificar si la impresora ya está en reposo después de los intentos
            await new Promise(resolve => setTimeout(resolve, 1000));
            const statusCheck = await this.getStatus();
            if (statusCheck) {
                const sts1 = statusCheck.raw?.sts1;
                const isNowWaiting = (sts1 === 0x40 || sts1 === 0x60);
                if (isNowWaiting) {
                    console.log("TfhkaDriver:: Impresora en reposo tras intentos de abort");
                    return true;
                }
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
            console.log("TfhkaDriver:: Enviando ENQ (0x05)");
            await this.connection.write(enqFrame);
            
            // Esperar 50ms como hace el SDK Python
            await new Promise(resolve => setTimeout(resolve, 50));
            
            // Leer exactamente 5 bytes (formato ENQ: STX|STS1|STS2|ETX|LRC)
            const response = await this.connection.read(500); // Timeout corto para ENQ
            if (!response) {
                console.error("TfhkaDriver:: No se recibió respuesta al ENQ");
                return null;
            }

            console.log("TfhkaDriver:: Respuesta ENQ recibida:", response.length, "bytes:", 
                Array.from(response).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' '));

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
        const TAX_MAP = {
            "0": " ",   // Exento (0x20)
            "1": "!",   // Tasa 1 General (0x21)
            "2": '"',   // Tasa 2 Reducida (0x22)
            "3": "#"    // Tasa 3 Adicional (0x23)
        };
        
        return TAX_MAP[String(fiscalCode)] || "!";
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
        const isWaiting = (sts1Before === 0x40 || sts1Before === 0x60);
        if (!isWaiting) {
            console.warn("TfhkaDriver:: Impresora no está en reposo (STS1=0x" + sts1Before?.toString(16) + "), intentando abortar...");
            const aborted = await this.abortTransaction();
            if (!aborted) {
                return {
                    success: false,
                    data: "",
                    error: "La impresora tiene una transacción previa abierta. Reiníciala y vuelve a intentarlo."
                };
            }
        }

        try {
            const commands = [];

            // Formato de números según flag 21 (default: "00" = estándar)
            const FLAG21_CONFIGS = {
                "00": { max_amount_int: 8,  max_amount_decimal: 2, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2 },
                "01": { max_amount_int: 7,  max_amount_decimal: 3, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2 },
                "02": { max_amount_int: 6,  max_amount_decimal: 4, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2 },
                "30": { max_amount_int: 14, max_amount_decimal: 2, max_qty_int: 14, max_qty_decimal: 3, max_payment_amount_int: 15, max_payment_amount_decimal: 2 },
            };
            const flag21Key = String(orderData.flag_21 || "00");
            const config = flag21Config || FLAG21_CONFIGS[flag21Key] || FLAG21_CONFIGS["00"];

            // 1. RIF del cliente
            const vat = orderData.partner?.vat || "V00000000";
            commands.push(`iR*${vat}`);

            // 2. Razón social del cliente
            const name = (orderData.partner?.name || "CLIENTE GENERICO").substring(0, 127);
            commands.push(`iS*${name}`);

            // 3. Información adicional (dirección, teléfono) - opcional
            let infoIndex = 0;
            if (orderData.partner?.address) {
                const addr = orderData.partner.address;
                const firstLine = addr.substring(0, 30);
                commands.push(`i${String(infoIndex).padStart(2, '0')}Direccion:${firstLine}`);
                infoIndex++;
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

            // 4. Items de la orden
            for (const line of orderData.lines || []) {
                if (line.price_unit <= 0) continue; // Descuentos negativos se manejan aparte

                const taxChar = this._getTaxCharacter(line.fiscal_code || "1");
                const price = this._formatAmount(line.price_unit, config.max_amount_int, config.max_amount_decimal);
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

            // 6. Pagos (parciales 2XX + cierre 1XX)
            const payments = orderData.payment_lines || [];
            let closingMethod = "01"; // Por defecto efectivo

            if (payments.length > 0) {
                // El método de cierre es el de mayor monto
                const mainPayment = payments.reduce((prev, cur) => cur.amount > prev.amount ? cur : prev);
                closingMethod = String(mainPayment.payment_method_code || "01").padStart(2, '0');

                // Enviar todos los pagos como parciales (2 + código + monto)
                for (const payment of payments) {
                    if (payment.amount > 0) {
                        const methodCode = String(payment.payment_method_code || "01").padStart(2, '0');
                        const amount = this._formatAmount(payment.amount, config.max_payment_amount_int, config.max_payment_amount_decimal);
                        commands.push(`2${methodCode}${amount}`);
                    }
                }
            }

            // 7. Abrir gaveta (si está configurado y pago es en efectivo)
            if (orderData.has_cashbox) {
                commands.push("w");
            }

            // 8. Cierre de documento (1 + código método principal)
            commands.push(`1${closingMethod}`);

            // 9. Líneas adicionales al pie (operador, número de pedido, etc.)
            if (orderData.additional_lines?.length > 0) {
                for (let i = 0; i < orderData.additional_lines.length; i++) {
                    commands.push(`i${String(i).padStart(2, '0')}${orderData.additional_lines[i]}`);
                }
            }

            // 10. Fin de documento
            commands.push("199");

            // Enviar comandos secuencialmente — sin checkStatus (ya lo hicimos arriba)
            console.log("TfhkaDriver:: Enviando factura con", commands.length, "comandos:", commands);

            for (const cmd of commands) {
                // Los comandos de datos (iR*, iS*, items, etc.) se envían sin checkStatus
                // porque la impresora estará en medio de una transacción (STS1=0x61)
                const result = await this.sendCommand(cmd, null, false);

                if (!result.success) {
                    console.error("TfhkaDriver:: Comando falló:", cmd, result.error);
                    // Intentar cancelar con 9 y luego 199
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

            console.log("TfhkaDriver:: Factura impresa correctamente. Nro:", invoiceNumber);
            return this._buildFiscalResponse("Factura impresa correctamente", invoiceNumber, s1Result.data);

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
        if (sts1 !== 0x40 && sts1 !== 0x60) {
            const aborted = await this.abortTransaction();
            if (!aborted) {
                return { success: false, data: "", error: "La impresora tiene una transacción previa abierta. Reiníciala." };
            }
        }

        try {
            const commands = [];

            const FLAG21_CONFIGS = {
                "00": { max_amount_int: 8,  max_amount_decimal: 2, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2 },
                "01": { max_amount_int: 7,  max_amount_decimal: 3, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2 },
                "02": { max_amount_int: 6,  max_amount_decimal: 4, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2 },
                "30": { max_amount_int: 14, max_amount_decimal: 2, max_qty_int: 14, max_qty_decimal: 3, max_payment_amount_int: 15, max_payment_amount_decimal: 2 },
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

            // 6. Dirección y teléfono del cliente (opcional)
            let infoIndex = 0;
            if (orderData.partner?.address) {
                const addr = orderData.partner.address;
                const firstLine = addr.substring(0, 30);
                commands.push(`i${String(infoIndex).padStart(2, '0')}Direccion:${firstLine}`);
                infoIndex++;

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

            // 7. Líneas informativas (operador, pedido, etc.)
            if (orderData.additional_lines?.length > 0) {
                for (const line of orderData.additional_lines) {
                    commands.push(`i${String(infoIndex).padStart(2, '0')}${line}`);
                    infoIndex++;
                }
            }

            // 8. Items de la devolución
            // NC usa "d" + código_fiscal_numérico + precio + qty + desc
            for (const line of orderData.lines || []) {
                if (line.price_unit <= 0) continue;

                const fiscalCode = String(line.fiscal_code || "1");
                const price = this._formatAmount(line.price_unit, config.max_amount_int, config.max_amount_decimal);
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

            // 10. Pagos
            const payments = orderData.payment_lines || [];
            let closingMethod = "01";

            if (payments.length > 0) {
                const mainPayment = payments.reduce((prev, cur) => cur.amount > prev.amount ? cur : prev);
                closingMethod = String(mainPayment.payment_method_code || "01").padStart(2, '0');

                for (const payment of payments) {
                    const methodCode = String(payment.payment_method_code || "01").padStart(2, '0');
                    // Enviar solo los pagos que NO sean el método principal (parciales)
                    if (payment.amount > 0 && methodCode !== closingMethod) {
                        const amount = this._formatAmount(payment.amount, config.max_payment_amount_int, config.max_payment_amount_decimal);
                        commands.push(`2${methodCode}${amount}`);
                    }
                }
            }

            // 11. Gaveta (si aplica)
            if (orderData.has_cashbox) {
                commands.push("w");
            }

            // 12. Cierre
            commands.push(`1${closingMethod}`);

            // 13. Fin de documento
            commands.push("199");

            console.log("TfhkaDriver:: Enviando nota de crédito con", commands.length, "comandos:", commands);

            for (const cmd of commands) {
                const result = await this.sendCommand(cmd, null, false);
                if (!result.success) {
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

            console.log("TfhkaDriver:: Nota de crédito impresa correctamente. Nro:", creditNoteNumber);
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
        if (sts1 !== 0x40 && sts1 !== 0x60) {
            const aborted = await this.abortTransaction();
            if (!aborted) {
                return { success: false, data: "", error: "La impresora tiene una transacción previa abierta. Reiníciala." };
            }
        }

        try {
            const commands = [];

            const FLAG21_CONFIGS = {
                "00": { max_amount_int: 8,  max_amount_decimal: 2, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2 },
                "01": { max_amount_int: 7,  max_amount_decimal: 3, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2 },
                "02": { max_amount_int: 6,  max_amount_decimal: 4, max_qty_int: 5,  max_qty_decimal: 3, max_payment_amount_int: 10, max_payment_amount_decimal: 2 },
                "30": { max_amount_int: 14, max_amount_decimal: 2, max_qty_int: 14, max_qty_decimal: 3, max_payment_amount_int: 15, max_payment_amount_decimal: 2 },
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

            // 6. Dirección del cliente (opcional)
            let infoIndex = 0;
            if (orderData.partner?.address) {
                const addr = orderData.partner.address;
                commands.push(`i${String(infoIndex).padStart(2, '0')}Direccion:${addr.substring(0, 30)}`);
                infoIndex++;
                if (addr.length > 30) {
                    commands.push(`i${String(infoIndex).padStart(2, '0')}${addr.substring(30, 70)}`);
                    infoIndex++;
                }
            }

            if (orderData.partner?.phone) {
                commands.push(`i${String(infoIndex).padStart(2, '0')}Telefono:${orderData.partner.phone}`);
                infoIndex++;
            }

            // 7. Información adicional
            if (orderData.additional_info?.length > 0) {
                for (const info of orderData.additional_info) {
                    commands.push(`i${String(infoIndex).padStart(2, '0')}${info}`);
                    infoIndex++;
                }
            }

            // 8. Items de la nota de débito
            // ND usa backtick (`) + código_fiscal_texto + precio + qty + desc
            for (const line of orderData.lines || []) {
                if (line.price_unit < 0) continue;

                const fiscalCode = String(line.fiscal_code || "1");
                const price = this._formatAmount(Math.abs(line.price_unit), config.max_amount_int, config.max_amount_decimal);
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

            // 10. Pagos
            const payments = orderData.payment_lines || [];
            let closingMethod = "01";

            // Agrupar pagos por método (sumar montos del mismo método)
            const groupedPayments = {};
            for (const p of payments) {
                const key = String(p.payment_method_code || "01").padStart(2, '0');
                groupedPayments[key] = (groupedPayments[key] || 0) + Math.abs(p.amount);
            }

            // Método de cierre = el de mayor monto
            if (Object.keys(groupedPayments).length > 0) {
                closingMethod = Object.entries(groupedPayments)
                    .reduce((a, b) => b[1] > a[1] ? b : a)[0];
            }

            // Enviar pagos parciales (los que no son el de cierre)
            for (const [methodCode, amount] of Object.entries(groupedPayments)) {
                if (amount > 0 && methodCode !== closingMethod) {
                    const amountStr = this._formatAmount(amount, config.max_payment_amount_int, config.max_payment_amount_decimal);
                    commands.push(`2${methodCode}${amountStr}`);
                }
            }

            // 11. Gaveta
            if (orderData.has_cashbox) {
                commands.push("w");
            }

            // 12. Cierre
            commands.push(`1${closingMethod}`);

            // 13. Líneas adicionales al pie
            if (orderData.additional_lines?.length > 0) {
                for (let i = 0; i < orderData.additional_lines.length; i++) {
                    commands.push(`i${String(i).padStart(2, '0')}${orderData.additional_lines[i]}`);
                }
            }

            // 14. Fin de documento
            commands.push("199");

            console.log("TfhkaDriver:: Enviando nota de débito con", commands.length, "comandos:", commands);

            for (const cmd of commands) {
                const result = await this.sendCommand(cmd, null, false);
                if (!result.success) {
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

            console.log("TfhkaDriver:: Nota de débito impresa correctamente. Nro:", debitNoteNumber);
            return this._buildFiscalResponse("Nota de débito impresa correctamente", debitNoteNumber, s1Result.data);

        } catch (error) {
            console.error("TfhkaDriver:: Error al imprimir nota de débito", error);
            await this.abortTransaction();
            return { success: false, data: "", error: error.message };
        }
    }
}
