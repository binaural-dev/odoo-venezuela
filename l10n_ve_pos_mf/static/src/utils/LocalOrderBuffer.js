/** @odoo-module */

/**
 * LocalOrderBuffer - Buffer offline para pedidos del POS
 * 
 * Almacena pedidos en localStorage cuando el backend de Odoo no está disponible.
 * Los pedidos se sincronizan automáticamente cuando se restablece la conexión.
 */
export class LocalOrderBuffer {
    static STORAGE_KEY = 'l10n_ve_pos_mf_unsynced_orders';
    static MAX_BUFFER_SIZE = 50;

    /**
     * Agrega un pedido al buffer offline
     * @param {Object} orderData - Datos del pedido (export_as_JSON)
     * @param {Object} fiscalData - Datos fiscales (serial, invoiceNumber, reportZ)
     */
    static add(orderData, fiscalData) {
        const buffer = this.getAll();
        
        if (buffer.length >= this.MAX_BUFFER_SIZE) {
            console.warn("LocalOrderBuffer:: Buffer lleno, descartando pedido más antiguo");
            buffer.shift();
        }
        
        buffer.push({
            orderData,
            fiscalData,
            timestamp: Date.now(),
            retries: 0,
        });
        
        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(buffer));
        } catch (e) {
            console.error("LocalOrderBuffer:: Error guardando en localStorage", e);
        }
    }

    /**
     * Obtiene todos los pedidos pendientes
     * @returns {Array}
     */
    static getAll() {
        try {
            const raw = localStorage.getItem(this.STORAGE_KEY);
            return raw ? JSON.parse(raw) : [];
        } catch {
            return [];
        }
    }

    /**
     * Retorna la cantidad de pedidos pendientes
     * @returns {number}
     */
    static count() {
        return this.getAll().length;
    }

    /**
     * Elimina un pedido específico del buffer
     * @param {number} index - Índice del pedido a eliminar
     */
    static remove(index) {
        const buffer = this.getAll();
        if (index >= 0 && index < buffer.length) {
            buffer.splice(index, 1);
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(buffer));
        }
    }

    /**
     * Actualiza un pedido específico del buffer (persiste en localStorage)
     * @param {number} index - Índice del pedido a actualizar
     * @param {Object} updates - Campos a actualizar (ej. { retries: 3 })
     */
    static update(index, updates) {
        const buffer = this.getAll();
        if (index >= 0 && index < buffer.length && updates) {
            buffer[index] = { ...buffer[index], ...updates };
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(buffer));
        }
    }

    /**
     * Limpia todo el buffer
     */
    static clear() {
        localStorage.removeItem(this.STORAGE_KEY);
    }

    /**
     * Verifica si hay pedidos pendientes de sincronizar
     * @returns {boolean}
     */
    static hasPending() {
        return this.count() > 0;
    }
}
