/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";
import { ConnectionLostError, rpc } from "@web/core/network/rpc";
import { browser } from "@web/core/browser/browser";

/**
 * Cola durable de reintento del REGISTRO de órdenes del Kiosko.
 *
 * Problema: el Kiosko de `pos_self_order` es online-first — desactiva IndexedDB
 * y la cola local del POS (`data_service.js`: no-op en modo kiosko) y registra
 * cada orden con un RPC bloqueante. Si el servidor Odoo no está accesible
 * (despliegues con Odoo remoto), una orden ya PAGADA (y ya impresa en la máquina
 * fiscal — ver `l10n_ve_pos_mf_self_order`) puede quedarse sin registrar.
 *
 * Solución (acotada, sin tocar el arranque del PosData): una cola propia en
 * `localStorage` — el mecanismo que el usuario aceptó explícitamente y que
 * `l10n_ve_pos_mf` ya usa (`LocalOrderHistory`). Guarda el payload EXACTO del
 * RPC que falló y lo reintenta automáticamente: al arrancar la app, al volver la
 * conexión (`online`) y con un timer (`pos.config.auto_sync_interval`).
 *
 * El RPC de finalización del Kiosko es idempotente (el pago se protege por
 * existencia de línea de pago; la factura por `account_move`), así que reintentar
 * el MISMO payload no duplica pago ni factura.
 *
 * La orden nunca se pierde: cuando el servidor vuelve, se registra y se factura
 * (con el `mf_invoice_number` ya impreso, vía `_prepare_invoice_vals`).
 */
patch(SelfOrder.prototype, {
    setup() {
        super.setup(...arguments);
        if (!this.kioskMode) {
            return;
        }
        // Reintento al arrancar (por si quedó algo de una sesión anterior) y
        // suscripción a "online" + timer periódico. Fire-and-forget.
        this.flushKioskRegistrations();
        this._kioskFlushBound = () => this.flushKioskRegistrations();
        browser.addEventListener("online", this._kioskFlushBound);
        const seconds = Number(this.config.auto_sync_interval) || 60;
        this._kioskFlushTimer = browser.setInterval(
            this._kioskFlushBound,
            Math.max(15, seconds) * 1000
        );
    },

    _kioskSyncKey() {
        return `l10n_ve_kiosk_sync_${this.config.id}`;
    },

    // Cola de FALLIDAS: órdenes que el servidor rechazó por un error de negocio
    // (no de red). NO se descartan NUNCA — quedan para acción manual (reintento
    // desde debug o respaldo de caja). Es la garantía de "no perder órdenes".
    _kioskFailedKey() {
        return `l10n_ve_kiosk_failed_${this.config.id}`;
    },

    _readLsArray(key) {
        try {
            const raw = browser.localStorage.getItem(key);
            const parsed = raw ? JSON.parse(raw) : [];
            return Array.isArray(parsed) ? parsed : [];
        } catch (error) {
            console.error("[Kiosk sync] almacenamiento ilegible", key, error);
            return [];
        }
    },

    _writeLsArray(key, arr) {
        try {
            browser.localStorage.setItem(key, JSON.stringify(arr));
        } catch (error) {
            console.error("[Kiosk sync] no se pudo persistir", key, error);
        }
    },

    _readKioskQueue() {
        return this._readLsArray(this._kioskSyncKey());
    },

    _writeKioskQueue(queue) {
        this._writeLsArray(this._kioskSyncKey(), queue);
    },

    _readKioskFailed() {
        return this._readLsArray(this._kioskFailedKey());
    },

    _writeKioskFailed(arr) {
        this._writeLsArray(this._kioskFailedKey(), arr);
    },

    _pushKioskFailed(entry) {
        const failed = this._readKioskFailed();
        if (failed.some((e) => e.uuid === entry.uuid)) {
            return;
        }
        failed.push({ ...entry, failedAt: Date.now() });
        this._writeKioskFailed(failed);
    },

    get kioskPendingCount() {
        return this._readKioskQueue().length;
    },

    get kioskFailedCount() {
        return this._readKioskFailed().length;
    },

    /**
     * Encola un registro fallido para reintentarlo luego. `entry` = {route,
     * order (ya serializada), access_token, payment_method_id, uuid}. Dedup por
     * uuid (idempotente).
     */
    enqueueKioskRegistration(entry) {
        if (!entry || !entry.route || !entry.uuid) {
            return;
        }
        const queue = this._readKioskQueue();
        if (queue.some((e) => e.uuid === entry.uuid)) {
            return;
        }
        queue.push({ ...entry, ts: Date.now() });
        this._writeKioskQueue(queue);
    },

    /**
     * Reintenta todos los registros pendientes. Si el servidor sigue caído
     * (ConnectionLostError) se detiene y CONSERVA la cola para el próximo
     * disparo. Si el registro entra, se elimina de pendientes. Un error de
     * negocio (no de red) NO se descarta: la entrada se MUEVE a la cola de
     * fallidas (`kioskFailed`) para acción manual — así una orden ya pagada e
     * impresa nunca se pierde silenciosamente.
     */
    async flushKioskRegistrations() {
        if (this._kioskFlushing) {
            return;
        }
        this._kioskFlushing = true;
        try {
            let queue = this._readKioskQueue();
            while (queue.length) {
                const entry = queue[0];
                try {
                    await rpc(entry.route, {
                        order: entry.order,
                        access_token: entry.access_token,
                        payment_method_id: entry.payment_method_id,
                    });
                } catch (error) {
                    if (error instanceof ConnectionLostError) {
                        // Servidor aún inaccesible: conservar y reintentar luego.
                        break;
                    }
                    // Error de negocio: NO descartar. Mover a fallidas.
                    console.error(
                        "[Kiosk sync] el servidor rechazó la orden; se mueve a FALLIDAS (no se pierde)",
                        entry.uuid,
                        error
                    );
                    this._pushKioskFailed({
                        ...entry,
                        errorMessage: String((error && error.message) || error),
                    });
                }
                // OK o movida a fallidas: sacar de pendientes.
                queue = this._readKioskQueue().filter((e) => e.uuid !== entry.uuid);
                this._writeKioskQueue(queue);
            }
        } finally {
            this._kioskFlushing = false;
        }
    },

    /**
     * Reintenta manualmente las órdenes que quedaron en FALLIDAS (p. ej. tras
     * corregir la causa del rechazo — diario de factura, etc.). Las devuelve a
     * la cola de pendientes y dispara el flush; las que sigan fallando vuelven a
     * fallidas (no se pierden).
     */
    async retryFailedKioskRegistrations() {
        const failed = this._readKioskFailed();
        if (!failed.length) {
            return;
        }
        const pending = this._readKioskQueue();
        const known = new Set(pending.map((e) => e.uuid));
        for (const entry of failed) {
            if (!known.has(entry.uuid)) {
                pending.push(entry);
            }
        }
        this._writeKioskQueue(pending);
        this._writeKioskFailed([]);
        await this.flushKioskRegistrations();
    },
});
