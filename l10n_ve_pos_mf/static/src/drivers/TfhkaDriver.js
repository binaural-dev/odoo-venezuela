/** @odoo-module */

import { SerialConnection } from "../core/SerialConnection";
import { FiscalProtocol } from "../core/FiscalProtocol";

/**
 * TfhkaDriver - Driver de alto nivel para impresoras fiscales The Factory HKA
 * 
 * Implementa los comandos específicos del protocolo TFHKA basados en:
 * Manual de Protocolos y Comandos v8.4.2 - Venezuela
 * 
 * Comandos principales:
 * - Facturación: I01 (factura), I02 (nota de crédito), I03 (nota de débito)
 * - Reportes: I0X (Reporte X), I0Z (Reporte Z)
 * - Estado: ENQ (consultar estado)
 * - Gaveta: 0 (abrir gaveta)
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
     * @returns {Promise<Object>} - { success: boolean, data: string, error: string }
     */
    async sendCommand(command, timeout = 5000) {
        if (!this.isConnected) {
            return { success: false, data: "", error: "Impresora no conectada" };
        }

        for (let attempt = 0; attempt < this.retryAttempts; attempt++) {
            try {
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
     * Consulta el estado de la impresora (comando ENQ)
     * @returns {Promise<Object|null>} - Estado parseado o null si falla
     */
    async getStatus() {
        try {
            const enqFrame = new Uint8Array([FiscalProtocol.ENQ]);
            await this.connection.write(enqFrame);
            
            const response = await this.connection.read(3000);
            if (!response) {
                return null;
            }

            const status = FiscalProtocol.parseStatus(response);
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
}
