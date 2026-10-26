/** @odoo-module */

/**
 * SerialConnection - Capa de transporte para comunicación serial con dispositivos fiscales
 * 
 * Maneja la conexión física con el puerto serial usando la Web Serial API.
 * Inspirado en om_datalogic/static/src/overrides/scale.js
 * 
 * Features:
 * - Administración de lock de lectura/escritura para evitar colisiones
 * - Configuración de baudRate, dataBits, stopBits, parity según protocolo RS232
 * - Persistencia de configuración en localStorage
 * - Gestión de streams (ReadableStream/WritableStream)
 */

export class SerialConnection {
    constructor() {
        this.port = null;
        this.reader = null;
        this.writer = null;
        this.readLock = false;
        this.writeLock = false;
        this.isConnected = false;
        
        // Configuración por defecto para TFHKA (RS232: 9600 8E1)
        // IMPORTANTE: TFHKA usa paridad PAR (even), no none
        this.config = {
            baudRate: 9600,
            dataBits: 8,
            stopBits: 1,
            parity: "even",      // ⚠️ CRÍTICO: TFHKA requiere paridad PAR
            flowControl: "none"  // Manual RTS/CTS se maneja por separado
        };
    }

    /**
     * Solicita permiso al usuario para conectarse a un puerto serial
     * @returns {Promise<boolean>} true si se conectó exitosamente
     */
    async requestPort() {
        try {
            if (!navigator.serial) {
                console.error("SerialConnection:: Web Serial API no soportada en este navegador");
                return false;
            }

            this.port = await navigator.serial.requestPort();
            
            await this.port.open(this.config);
            this.isConnected = true;
            
            // Guardar la configuración en localStorage para reconexión automática
            this._savePortConfig();
            
            return true;
        } catch (error) {
            console.error("SerialConnection:: Error al conectar puerto serial", error);
            this.isConnected = false;
            return false;
        }
    }

    /**
     * Intenta reconectar automáticamente al último puerto usado
     * @returns {Promise<boolean>}
     */
    async autoConnect() {
        try {
            if (!navigator.serial) {
                return false;
            }

            const ports = await navigator.serial.getPorts();
            if (ports.length > 0) {
                this.port = ports[0];
                await this.port.open(this.config);
                this.isConnected = true;
                return true;
            }
            return false;
        } catch (error) {
            console.error("SerialConnection:: Error en reconexión automática", error);
            return false;
        }
    }

    /**
     * Escribe datos al puerto serial (con lock para evitar colisiones)
     * @param {Uint8Array} data - Datos binarios a enviar
     * @returns {Promise<boolean>}
     */
    async write(data) {
        if (!this.isConnected || !this.port) {
            console.error("SerialConnection:: Puerto no conectado");
            return false;
        }

        let waitCount = 0;
        while (this.writeLock && waitCount < 500) {
            await new Promise(resolve => setTimeout(resolve, 10));
            waitCount++;
        }
        if (waitCount >= 500) {
            console.error("SerialConnection:: Timeout esperando writeLock");
            this.writeLock = false;
        }

        try {
            this.writeLock = true;
            this.writer = this.port.writable.getWriter();
            await this.writer.write(data);
            this.writer.releaseLock();
            this.writeLock = false;
            return true;
        } catch (error) {
            console.error("SerialConnection:: Error al escribir en puerto serial", error);
            if (this.writer) {
                try {
                    this.writer.releaseLock();
                } catch (e) {}
            }
            this.writeLock = false;
            return false;
        }
    }

    /**
     * Lee datos del puerto serial hasta encontrar un delimitador o timeout
     * @param {number} timeout - Tiempo máximo de espera en ms (default: 5000)
     * @param {string} delimiter - Carácter de fin de lectura (default: ETX 0x03)
     * @returns {Promise<Uint8Array|null>}
     */
    async read(timeout = 5000, delimiter = "\x03") {
        if (!this.isConnected || !this.port) {
            console.error("SerialConnection:: Puerto no conectado");
            return null;
        }

        // Esperar si hay un lock de lectura activo
        let waitCount = 0;
        while (this.readLock && waitCount < 500) {
            await new Promise(resolve => setTimeout(resolve, 10));
            waitCount++;
        }
        if (waitCount >= 500) {
            console.error("SerialConnection:: Timeout esperando readLock en read()");
            this.readLock = false;
        }

        let timeoutId = null;
        let timedOut = false;
        try {
            this.readLock = true;
            const chunks = [];
            const decoder = new TextDecoder();
            let buffer = "";

            this.reader = this.port.readable.getReader();

            let readResolve;
            const readPromise = new Promise((resolve) => { readResolve = resolve; });

            timeoutId = setTimeout(() => {
                timedOut = true;
                readResolve();
            }, timeout);

            (async () => {
                try {
                    while (true) {
                        const { value, done } = await this.reader.read();
                        if (done) {
                            break;
                        }

                        chunks.push(value);

                        if (value.length === 1 && (value[0] === 0x06 || value[0] === 0x15)) {
                            break;
                        }

                        buffer += decoder.decode(value, { stream: true });

                        if (buffer.includes(delimiter)) {
                            break;
                        }
                    }
                } catch (e) {
                    console.error("SerialConnection:: Error en read loop:", e);
                }
                readResolve();
            })();

            await readPromise;

            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }

            if (timedOut) {
                return null;
            }

            // Concatenar todos los chunks en un solo Uint8Array
            const totalLength = chunks.reduce((acc, chunk) => acc + chunk.length, 0);
            const result = new Uint8Array(totalLength);
            let offset = 0;
            for (const chunk of chunks) {
                result.set(chunk, offset);
                offset += chunk.length;
            }

            return result;
        } catch (error) {
            console.error("SerialConnection:: Error al leer del puerto serial", error);
            return null;
        } finally {
            if (timeoutId) {
                clearTimeout(timeoutId);
            }
            if (this.reader) {
                try {
                    await this.reader.cancel();
                } catch (e) {}
                try {
                    this.reader.releaseLock();
                } catch (e) {}
            }
            this.readLock = false;
        }
    }

    /**
     * Limpia el buffer de lectura (descarta datos residuales)
     * Equivalente a pySerial: flushInput() + flushOutput()
     * @returns {Promise<void>}
     */
    async flushBuffer() {
        if (!this.isConnected || !this.port) {
            return;
        }

        let waitCount = 0;
        while ((this.readLock || this.writeLock) && waitCount < 50) {
            await new Promise(resolve => setTimeout(resolve, 10));
            waitCount++;
        }

        if (waitCount >= 50) {
            console.warn("SerialConnection:: Timeout esperando locks para flush");
            this.readLock = false;
            this.writeLock = false;
            return;
        }

        let bytesDiscarded = 0;
        let flushReader = null;

        try {
            this.readLock = true;
            flushReader = this.port.readable.getReader();

            let flushResolve;
            const flushDone = new Promise((resolve) => { flushResolve = resolve; });
            let flushTimeoutId = setTimeout(() => { flushResolve(); }, 60);

            (async () => {
                try {
                    for (let i = 0; i < 10; i++) {
                        const readPromise = flushReader.read();
                        const shortTimeout = new Promise((resolve) => setTimeout(() => resolve(null), 15));

                        try {
                            const result = await Promise.race([readPromise, shortTimeout]);
                            if (!result || result.done || !result.value || result.value.length === 0) {
                                break;
                            }
                            bytesDiscarded += result.value.length;
                        } catch (e) {
                            break;
                        }
                    }
                } catch (e) {}
                flushResolve();
            })();

            await flushDone;
            if (flushTimeoutId) {
                clearTimeout(flushTimeoutId);
                flushTimeoutId = null;
            }

        } catch (error) {
            console.warn("SerialConnection:: Error al limpiar buffer de lectura", error);
        } finally {
            if (flushReader) {
                try {
                    await flushReader.cancel();
                } catch (e) {}
                await new Promise(resolve => setTimeout(resolve, 10));
                try {
                    flushReader.releaseLock();
                } catch (e) {}
            }
            this.readLock = false;
        }

        try {
            while (this.writeLock) {
                await new Promise(resolve => setTimeout(resolve, 10));
            }
        } catch (error) {
            console.warn("SerialConnection:: Error esperando write lock", error);
        }
    }

    /**
     * Cierra la conexión serial y libera recursos
     * @returns {Promise<void>}
     */
    async disconnect() {
        try {
            // Liberar locks si están activos
            if (this.reader) {
                try {
                    await this.reader.cancel();
                    this.reader.releaseLock();
                } catch (e) {
                    // Ignorar
                }
                this.reader = null;
            }

            if (this.writer) {
                try {
                    this.writer.releaseLock();
                } catch (e) {
                    // Ignorar
                }
                this.writer = null;
            }

            if (this.port) {
                await this.port.close();
                this.port = null;
            }

            this.isConnected = false;
            this.readLock = false;
            this.writeLock = false;

        } catch (error) {
            console.error("SerialConnection:: Error al desconectar puerto serial", error);
        }
    }

    /**
     * Guarda la configuración del puerto en localStorage
     * @private
     */
    _savePortConfig() {
        try {
            localStorage.setItem("fiscal_printer_config", JSON.stringify(this.config));
        } catch (error) {
            console.error("SerialConnection:: Error al guardar configuración", error);
        }
    }

    /**
     * Carga la configuración del puerto desde localStorage
     * @private
     */
    _loadPortConfig() {
        try {
            const saved = localStorage.getItem("fiscal_printer_config");
            if (saved) {
                this.config = { ...this.config, ...JSON.parse(saved) };
            }
        } catch (error) {
            console.error("SerialConnection:: Error al cargar configuración", error);
        }
    }
}
