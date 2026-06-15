/** @odoo-module */

import { StatusParser } from "./StatusParser";

/**
 * FiscalProtocol - Capa de protocolo para impresoras fiscales TFHKA
 * 
 * Implementa el protocolo de comunicación definido en el Manual de Protocolos y Comandos:
 * - Estructura de trama: <STX 0x02> + DATA + <ETX 0x03> + LRC
 * - LRC (Longitudinal Redundancy Check): XOR de todos los bytes entre STX y ETX (inclusive)
 * - ACK (0x06): Comando recibido correctamente
 * - NAK (0x15): Error en transmisión, reenviar
 * 
 * Referencias:
 * - Manual TFHKA v8.4.2, Sección: "ESTRUCTURA DE LA TRAMA DE COMUNICACIÓN"
 */

export class FiscalProtocol {
    
    // Caracteres de control ASCII
    static STX = 0x02;  // Start of Text
    static ETX = 0x03;  // End of Text
    static ACK = 0x06;  // Acknowledge
    static NAK = 0x15;  // Negative Acknowledge
    static ENQ = 0x05;  // Enquiry (solicitar estado)

    /**
     * Construye una trama completa para enviar a la impresora fiscal
     * @param {string} command - Comando ASCII (ej: "I01", "U0X", etc.)
     * @returns {Uint8Array} - Trama binaria lista para enviar por serial
     */
    static buildFrame(command) {
        const encoder = new TextEncoder();
        const commandBytes = encoder.encode(command);
        
        // Construir: STX + COMMAND + ETX
        const frameWithoutLRC = new Uint8Array(1 + commandBytes.length + 1);
        frameWithoutLRC[0] = FiscalProtocol.STX;
        frameWithoutLRC.set(commandBytes, 1);
        frameWithoutLRC[frameWithoutLRC.length - 1] = FiscalProtocol.ETX;
        
        // Calcular LRC (XOR de todos los bytes, incluyendo STX y ETX)
        const lrc = FiscalProtocol.calculateLRC(frameWithoutLRC);
        
        // Trama final: STX + COMMAND + ETX + LRC
        const frame = new Uint8Array(frameWithoutLRC.length + 1);
        frame.set(frameWithoutLRC, 0);
        frame[frame.length - 1] = lrc;
        
        return frame;
    }

    /**
     * Calcula el LRC (Longitudinal Redundancy Check) usando XOR
     * @param {Uint8Array} data - Bytes desde STX hasta ETX (inclusive)
     * @returns {number} - Byte de LRC
     */
    static calculateLRC(data) {
        let lrc = 0;
        for (let i = 0; i < data.length; i++) {
            lrc ^= data[i];
        }
        return lrc;
    }

    /**
     * Valida una respuesta recibida de la impresora
     * @param {Uint8Array} response - Respuesta binaria del puerto serial
     * @returns {Object} - { valid: boolean, data: string, error: string }
     */
    static parseResponse(response) {
        if (!response || response.length < 3) {
            return { valid: false, data: "", error: "Respuesta vacía o incompleta" };
        }

        // Verificar que empiece con STX
        if (response[0] !== FiscalProtocol.STX) {
            return { valid: false, data: "", error: "Respuesta no comienza con STX" };
        }

        // Buscar posición de ETX
        let etxIndex = -1;
        for (let i = 1; i < response.length; i++) {
            if (response[i] === FiscalProtocol.ETX) {
                etxIndex = i;
                break;
            }
        }

        if (etxIndex === -1) {
            return { valid: false, data: "", error: "No se encontró ETX en la respuesta" };
        }

        // Verificar que haya espacio para el LRC
        if (etxIndex + 1 >= response.length) {
            return { valid: false, data: "", error: "Falta byte de LRC" };
        }

        // Extraer LRC recibido
        const receivedLRC = response[etxIndex + 1];
        
        // Calcular LRC esperado (desde STX hasta ETX inclusive)
        const frameData = response.slice(0, etxIndex + 1);
        const calculatedLRC = FiscalProtocol.calculateLRC(frameData);

        // Verificar LRC
        if (receivedLRC !== calculatedLRC) {
            return { 
                valid: false, 
                data: "", 
                error: `LRC inválido. Esperado: ${calculatedLRC.toString(16)}, Recibido: ${receivedLRC.toString(16)}` 
            };
        }

        // Extraer datos (entre STX y ETX, excluyéndolos)
        const dataBytes = response.slice(1, etxIndex);
        const decoder = new TextDecoder();
        const data = decoder.decode(dataBytes);

        return { valid: true, data: data, error: "" };
    }

    /**
     * Construye un comando de consulta de estado (ENQ)
     * @returns {Uint8Array}
     */
    static buildStatusRequest() {
        return new Uint8Array([FiscalProtocol.ENQ]);
    }

    /**
     * Verifica si la respuesta es un ACK (comando aceptado)
     * @param {Uint8Array} response
     * @returns {boolean}
     */
    static isACK(response) {
        return response && response.length > 0 && response[0] === FiscalProtocol.ACK;
    }

    /**
     * Verifica si la respuesta es un NAK (error, reenviar)
     * @param {Uint8Array} response
     * @returns {boolean}
     */
    static isNAK(response) {
        return response && response.length > 0 && response[0] === FiscalProtocol.NAK;
    }

    /**
     * Parsea el status de la impresora (respuesta a comando de lectura de estado)
     * Formato: <STX>status_bytes<ETX><LRC>
     * @param {Uint8Array} response
     * @returns {Object} - { fiscal_memory_ok, paper_ok, drawer_closed, ... }
     */
    /**
     * Parsea la respuesta de ENQ (consulta de estado)
     * Formato: STX(0x02) | STS1 | STS2 | ETX(0x03) | LRC
     * LRC = STS1 ^ STS2 ^ ETX
     * @param {Uint8Array} response - 5 bytes
     * @returns {Object} - Status parseado o error
     */
    static parseStatusENQ(response) {
        if (!response || response.length < 5) {
            console.error("FiscalProtocol:: Respuesta ENQ incompleta, esperaba 5 bytes, recibió:", response ? response.length : 0);
            return null;
        }

        const stx = response[0];
        const sts1 = response[1];
        const sts2 = response[2];
        const etx = response[3];
        const lrc = response[4];

        // Verificar STX y ETX
        if (stx !== FiscalProtocol.STX) {
            console.error("FiscalProtocol:: STX inválido en respuesta ENQ:", stx);
        }
        if (etx !== FiscalProtocol.ETX) {
            console.error("FiscalProtocol:: ETX inválido en respuesta ENQ:", etx);
        }

        // Verificar LRC: STS1 ^ STS2 ^ ETX
        const expectedLRC = sts1 ^ sts2 ^ etx;
        if (lrc !== expectedLRC) {
            console.error("FiscalProtocol:: LRC inválido en respuesta ENQ. Esperado:", expectedLRC, "Recibido:", lrc);
            return null;
        }

        console.log("FiscalProtocol:: ENQ parseado correctamente - STS1:", sts1.toString(16), "STS2:", sts2.toString(16));

        // Parsear usando StatusParser (que ya tiene toda la lógica de bits)
        // Construir un mock frame para StatusParser: STX|STS1|STS2|ETX|LRC
        const mockFrame = new Uint8Array([FiscalProtocol.STX, sts1, sts2, FiscalProtocol.ETX, lrc]);
        return StatusParser.parse(mockFrame);
    }

    static parseStatus(response) {
        // DEPRECATED: Usar parseStatusENQ() en su lugar
        const parsed = FiscalProtocol.parseResponse(response);
        if (!parsed.valid) {
            return { error: parsed.error };
        }

        // El status viene en bytes hexadecimales (según manual TFHKA)
        // Ejemplo: "00000000" significa todo OK
        const statusHex = parsed.data;
        
        // TODO: Implementar parsing completo según tabla de estados del manual
        // Por ahora, retornamos el raw status
        return {
            raw: statusHex,
            fiscal_memory_ok: statusHex[0] === '0',
            paper_ok: statusHex[1] === '0',
            // ... más flags según el manual
        };
    }

    /**
     * Convierte una trama binaria a string hexadecimal para debugging
     * @param {Uint8Array} frame
     * @returns {string}
     */
    static frameToHex(frame) {
        return Array.from(frame)
            .map(b => b.toString(16).padStart(2, '0'))
            .join(' ');
    }

    /**
     * Convierte una trama binaria a string ASCII para debugging
     * @param {Uint8Array} frame
     * @returns {string}
     */
    static frameToASCII(frame) {
        const decoder = new TextDecoder();
        return decoder.decode(frame)
            .split('')
            .map(c => {
                const code = c.charCodeAt(0);
                if (code === FiscalProtocol.STX) return '<STX>';
                if (code === FiscalProtocol.ETX) return '<ETX>';
                if (code === FiscalProtocol.ACK) return '<ACK>';
                if (code === FiscalProtocol.NAK) return '<NAK>';
                if (code === FiscalProtocol.ENQ) return '<ENQ>';
                if (code < 32) return `<0x${code.toString(16)}>`;
                return c;
            })
            .join('');
    }
}
