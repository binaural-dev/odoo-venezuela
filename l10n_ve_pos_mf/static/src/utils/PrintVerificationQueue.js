/** @odoo-module */

import { session } from "@web/session";

/**
 * Pedidos cuya impresión fiscal quedó sin confirmar (el driver devolvió
 * `printed: null`). Se guardan en el navegador, que es el que habla con la
 * máquina, para resolverlos antes de imprimir cualquier otro documento: la
 * verificación compara los contadores de S1 con los de antes de esa
 * impresión, y deja de servir si se emite otro documento en el medio
 * (ver TfhkaDriver.verifyDocument). Tarea 85447.
 *
 * Cada entrada: { uuid, verification, resolved?, createdAt }. `resolved`
 * guarda el resultado de la máquina cuando ya se verificó pero todavía no se
 * pudo guardar en el servidor (sin conexión).
 *
 * La clave lleva la base de datos: varias bases en el mismo dominio no
 * comparten la cola.
 */
export class PrintVerificationQueue {
    static get STORAGE_KEY() {
        const key = "l10n_ve_pos_mf_print_verifications";
        return session.db ? `${key}:${session.db}` : key;
    }

    static getAll() {
        try {
            const raw = localStorage.getItem(this.STORAGE_KEY);
            const entries = raw ? JSON.parse(raw) : [];
            // Se ignora lo que no tenga forma de entrada (almacenamiento dañado).
            return Array.isArray(entries)
                ? entries.filter((entry) => entry && typeof entry === "object" && entry.uuid)
                : [];
        } catch {
            return [];
        }
    }

    static _save(entries) {
        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(entries));
        } catch (error) {
            console.error("PrintVerificationQueue:: No se pudo guardar la cola", error);
        }
    }

    static add(uuid, verification) {
        const entries = this.getAll().filter((entry) => entry.uuid !== uuid);
        entries.push({ uuid, verification, createdAt: new Date().toISOString() });
        this._save(entries);
    }

    static markResolved(uuid, resolved) {
        this._save(
            this.getAll().map((entry) => (entry.uuid === uuid ? { ...entry, resolved } : entry))
        );
    }

    static remove(uuid) {
        this._save(this.getAll().filter((entry) => entry.uuid !== uuid));
    }
}
