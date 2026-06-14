/** @odoo-module */

import { FiscalProtocol } from "../core/FiscalProtocol";

/**
 * MockSerialConnection - Mock de SerialConnection para testing
 * 
 * Simula el comportamiento de una impresora fiscal TFHKA sin hardware real.
 * Permite inyectar respuestas pre-programadas y condiciones de error para testing.
 * 
 * Uso en tests:
 * ```javascript
 * const mockConnection = new MockSerialConnection();
 * mockConnection.setNextResponse("ACK");
 * mockConnection.setStatus({ paperOk: false }); // Simular sin papel
 * ```
 */
export class MockSerialConnection {
    constructor() {
        this.isConnected = false;
        this.sentCommands = []; // Historial de comandos enviados
        this.responseQueue = []; // Cola de respuestas a devolver
        this.currentStatus = {
            // STS1 - Estado
            fiscalMode: true,
            fiscalMemoryNearFull: false,
            fiscalMemoryFull: false,
            bufferFull: false,
            nonFiscalTransactionInProgress: false,
            fiscalTransactionInProgress: false,
            
            // STS2 - Errores
            criticalError: false,
            drawerError: false,
            printerError: false,
            paperError: false,
            fiscalMemoryError: false,
        };
        
        // Configuración de delays para simular latencia real
        this.writeDelay = 10; // ms
        this.readDelay = 50; // ms
    }

    /**
     * Simula conexión al puerto serial
     */
    async requestPort() {
        await this._delay(100);
        this.isConnected = true;
        return true;
    }

    /**
     * Simula reconexión automática
     */
    async autoConnect() {
        await this._delay(50);
        this.isConnected = true;
        return true;
    }

    /**
     * Simula escritura al puerto serial
     */
    async write(data) {
        if (!this.isConnected) {
            return false;
        }

        await this._delay(this.writeDelay);
        
        // Registrar el comando enviado para verificación en tests
        const decoder = new TextDecoder();
        const commandText = decoder.decode(data);
        this.sentCommands.push({
            raw: data,
            text: commandText,
            ascii: FiscalProtocol.frameToASCII(data),
            hex: FiscalProtocol.frameToHex(data),
            timestamp: Date.now()
        });

        return true;
    }

    /**
     * Simula lectura del puerto serial
     */
    async read(timeout = 5000, delimiter = "\x03") {
        if (!this.isConnected) {
            return null;
        }

        await this._delay(this.readDelay);

        // Si hay respuestas en cola, devolver la siguiente
        if (this.responseQueue.length > 0) {
            const response = this.responseQueue.shift();
            
            // Si es un string especial, convertirlo a bytes
            if (typeof response === 'string') {
                return this._stringToBytes(response);
            }
            
            return response;
        }

        // Respuesta por defecto: ACK
        return new Uint8Array([FiscalProtocol.ACK]);
    }

    /**
     * Simula desconexión
     */
    async disconnect() {
        await this._delay(10);
        this.isConnected = false;
        this.sentCommands = [];
        this.responseQueue = [];
    }

    // ========== MÉTODOS PARA CONFIGURAR EL MOCK ==========

    /**
     * Establece la siguiente respuesta a devolver
     * @param {string|Uint8Array} response - "ACK", "NAK", o trama completa
     */
    setNextResponse(response) {
        if (response === "ACK") {
            this.responseQueue.push(new Uint8Array([FiscalProtocol.ACK]));
        } else if (response === "NAK") {
            this.responseQueue.push(new Uint8Array([FiscalProtocol.NAK]));
        } else if (response === "STATUS") {
            this.responseQueue.push(this._buildStatusResponse());
        } else if (typeof response === 'string') {
            // Construir trama completa con STX/ETX/LRC
            this.responseQueue.push(FiscalProtocol.buildFrame(response));
        } else {
            this.responseQueue.push(response);
        }
    }

    /**
     * Configura múltiples respuestas en secuencia
     * @param {Array} responses
     */
    setResponseSequence(responses) {
        responses.forEach(r => this.setNextResponse(r));
    }

    /**
     * Configura el estado de la impresora (para simular errores)
     * @param {Object} status
     */
    setStatus(status) {
        this.currentStatus = { ...this.currentStatus, ...status };
    }

    /**
     * Obtiene el historial de comandos enviados
     */
    getSentCommands() {
        return this.sentCommands;
    }

    /**
     * Obtiene el último comando enviado
     */
    getLastCommand() {
        return this.sentCommands[this.sentCommands.length - 1];
    }

    /**
     * Limpia el historial de comandos
     */
    clearHistory() {
        this.sentCommands = [];
    }

    /**
     * Verifica si se envió un comando específico
     * @param {string} commandPattern - Patrón regex o string exacto
     */
    wasCommandSent(commandPattern) {
        const regex = new RegExp(commandPattern);
        return this.sentCommands.some(cmd => regex.test(cmd.text));
    }

    // ========== MÉTODOS PRIVADOS ==========

    /**
     * Construye una respuesta de status basada en currentStatus
     */
    _buildStatusResponse() {
        // Construir STS1 (byte de estado)
        let sts1 = 0x40; // Base: 01000000
        if (this.currentStatus.fiscalMode) sts1 |= 0x04; // Bit 2
        if (this.currentStatus.fiscalMemoryNearFull) sts1 |= 0x08; // Bit 3
        if (this.currentStatus.fiscalMemoryFull) sts1 |= 0x10; // Bit 4
        if (this.currentStatus.bufferFull) sts1 |= 0x20; // Bit 5
        if (this.currentStatus.nonFiscalTransactionInProgress) sts1 |= 0x40; // Bit 6
        if (this.currentStatus.fiscalTransactionInProgress) sts1 |= 0x80; // Bit 7

        // Construir STS2 (byte de error)
        let sts2 = 0x40; // Base: 01000000 (sin errores)
        if (this.currentStatus.criticalError) sts2 |= 0x04; // Bit 2
        if (this.currentStatus.drawerError) sts2 |= 0x08; // Bit 3
        if (this.currentStatus.printerError) sts2 |= 0x10; // Bit 4
        if (this.currentStatus.paperError) sts2 |= 0x40; // Bit 6
        if (this.currentStatus.fiscalMemoryError) sts2 |= 0x04; // Bit 2

        // Construir trama: STX + STS1 + STS2 + ETX + LRC
        const data = new Uint8Array([
            FiscalProtocol.STX,
            sts1,
            sts2,
            FiscalProtocol.ETX
        ]);

        const lrc = FiscalProtocol.calculateLRC(data);
        const response = new Uint8Array(data.length + 1);
        response.set(data, 0);
        response[response.length - 1] = lrc;

        return response;
    }

    /**
     * Convierte un string a Uint8Array
     */
    _stringToBytes(str) {
        const encoder = new TextEncoder();
        return encoder.encode(str);
    }

    /**
     * Simula delay asíncrono
     */
    async _delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}
