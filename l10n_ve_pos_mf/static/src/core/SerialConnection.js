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
            
            // Obtener info del puerto (útil para debug)
            const info = this.port.getInfo();
            console.log("SerialConnection:: Puerto seleccionado:", {
                usbVendorId: info.usbVendorId ? `0x${info.usbVendorId.toString(16)}` : 'N/A',
                usbProductId: info.usbProductId ? `0x${info.usbProductId.toString(16)}` : 'N/A',
            });
            
            await this.port.open(this.config);
            this.isConnected = true;
            
            // Guardar la configuración en localStorage para reconexión automática
            this._savePortConfig();
            
            console.log("SerialConnection:: Puerto serial conectado con config:", this.config);
            console.log("SerialConnection:: TIP: Si tienes timeouts, prueba conectar la impresora directamente (sin hub USB)");
            
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
                console.log("SerialConnection:: Reconexión automática exitosa");
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

        // Esperar si hay un lock de escritura activo
        while (this.writeLock) {
            await new Promise(resolve => setTimeout(resolve, 10));
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
                } catch (e) {
                    // Ignorar error de unlock si ya estaba liberado
                }
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
        while (this.readLock) {
            await new Promise(resolve => setTimeout(resolve, 10));
        }

        try {
            this.readLock = true;
            const chunks = [];
            const decoder = new TextDecoder();
            let buffer = "";

            this.reader = this.port.readable.getReader();
            
            const timeoutPromise = new Promise((_, reject) => 
                setTimeout(() => reject(new Error("Timeout")), timeout)
            );

            const readPromise = (async () => {
                while (true) {
                    const { value, done } = await this.reader.read();
                    if (done) {
                        console.log("SerialConnection:: Stream cerrado");
                        break;
                    }
                    
                    console.log("SerialConnection:: Recibidos", value.length, "bytes:", 
                        Array.from(value).map(b => '0x' + b.toString(16).padStart(2, '0')).join(' '));
                    
                    chunks.push(value);
                    
                    // Si recibimos ACK (0x06) o NAK (0x15), retornar inmediatamente
                    if (value.length === 1 && (value[0] === 0x06 || value[0] === 0x15)) {
                        console.log(`SerialConnection:: Recibido ${value[0] === 0x06 ? 'ACK' : 'NAK'}`);
                        break;
                    }
                    
                    buffer += decoder.decode(value, { stream: true });
                    
                    // Salir si encontramos el delimitador
                    if (buffer.includes(delimiter)) {
                        console.log("SerialConnection:: Delimitador encontrado");
                        break;
                    }
                }
            })();

            await Promise.race([readPromise, timeoutPromise]);
            
            this.reader.releaseLock();
            this.readLock = false;

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
            if (this.reader) {
                try {
                    await this.reader.cancel();
                    this.reader.releaseLock();
                } catch (e) {
                    // Ignorar error de unlock si ya estaba liberado
                }
            }
            this.readLock = false;
            return null;
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

        // Esperar si hay locks activos
        let waitCount = 0;
        while ((this.readLock || this.writeLock) && waitCount < 50) {
            await new Promise(resolve => setTimeout(resolve, 10));
            waitCount++;
        }

        if (waitCount >= 50) {
            console.warn("SerialConnection:: Timeout esperando locks para flush");
            return;
        }

        let bytesDiscarded = 0;

        try {
            // PASO 1: Limpiar input buffer (lectura)
            this.readLock = true;
            const reader = this.port.readable.getReader();
            
            // Intentar leer datos disponibles con timeout de 50ms
            const timeoutPromise = new Promise((_, reject) => 
                setTimeout(() => reject(new Error("Flush timeout")), 50)
            );
            
            const flushPromise = (async () => {
                try {
                    // Leer hasta que no haya más datos inmediatamente disponibles
                    for (let i = 0; i < 10; i++) {
                        const readPromise = reader.read();
                        const shortTimeout = new Promise((_, reject) => 
                            setTimeout(() => reject(new Error("No more data")), 10)
                        );
                        
                        try {
                            const { value, done } = await Promise.race([readPromise, shortTimeout]);
                            if (done || !value || value.length === 0) {
                                break;
                            }
                            bytesDiscarded += value.length;
                        } catch (e) {
                            // No más datos disponibles
                            break;
                        }
                    }
                } catch (e) {
                    // Ignorar errores de lectura durante flush
                }
            })();

            try {
                await Promise.race([flushPromise, timeoutPromise]);
            } catch (e) {
                // Timeout es normal, significa que no hay datos
            }
            
            // Cancelar cualquier lectura pendiente
            try {
                await reader.cancel();
            } catch (e) {
                // Ignorar error de cancel
            }
            
            reader.releaseLock();
            this.readLock = false;

            if (bytesDiscarded > 0) {
                console.log(`SerialConnection:: Buffer limpiado: ${bytesDiscarded} bytes descartados`);
            }

        } catch (error) {
            console.warn("SerialConnection:: Error al limpiar buffer de lectura", error);
            this.readLock = false;
        }

        // PASO 2: Limpiar output buffer (escritura)
        // En Web Serial API no hay equivalente directo a flushOutput(),
        // pero podemos esperar a que el write lock esté liberado
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

            console.log("SerialConnection:: Puerto serial desconectado");
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
