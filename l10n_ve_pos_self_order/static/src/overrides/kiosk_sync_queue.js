/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";
import { ConnectionLostError, rpc } from "@web/core/network/rpc";
import { browser } from "@web/core/browser/browser";
import IndexedDB from "@point_of_sale/app/models/utils/indexed_db";

/**
 * Cola durable de reintento del REGISTRO de órdenes del Kiosko, en IndexedDB.
 *
 * El Kiosko de `pos_self_order` es online-first: desactiva el IndexedDB del
 * `PosData` (`data_service.js`: no-op en modo kiosko) y registra cada orden con
 * un RPC bloqueante. Si el servidor Odoo no está accesible, una orden ya pagada
 * (y ya impresa en la máquina fiscal) puede quedarse sin registrar.
 *
 * Aquí se guarda esa orden en una base **IndexedDB propia y dedicada** —igual que
 * hace el PoS normal con sus órdenes offline, pero SIN reactivar el `PosData`
 * (que también cachearía el dataset del servidor, algo que el Kiosko apaga a
 * propósito por ser desatendido). Se reutiliza la MISMA clase `IndexedDB` del POS.
 *
 * Dos stores (clave `uuid`):
 *  - `pending`: registros a reintentar (corte de red) — reintento automático al
 *    arrancar, en `online` y por timer (`auto_sync_interval`).
 *  - `failed`: registros rechazados por el servidor (error de negocio, NO de red)
 *    — NO se descartan nunca; reintento manual desde el menú Debug MF.
 *
 * Nota (recuperación de factura): desde `l10n-ve-pos-self-order-kiosk-invoice-recovery`,
 * un rechazo de FACTURACIÓN ya no llega aquí. `pos.order._process_saved_order`
 * (server-side) aísla la factura en un savepoint: si falla, la orden se crea y
 * queda PAGADA pendiente de facturar en el servidor (no rechaza el registro), así
 * que el RPC responde OK y la orden nunca entra a `failed`. Esta cola `failed`
 * queda para rechazos FATALES del registro completo (token inválido, payload
 * corrupto). Las pendientes de facturar se resuelven desde el panel de órdenes
 * fiscales (botón "Crear factura") o el menú de backend, no desde aquí.
 *
 * El RPC de finalización del Kiosko es idempotente, así que reintentar el MISMO
 * payload no duplica pago ni factura. El `mf_invoice_number` (si la orden se
 * imprimió offline) viaja en el payload, así llega a Odoo con la orden.
 */

const PENDING = "pending";
const FAILED = "failed";

patch(SelfOrder.prototype, {
    setup() {
        super.setup(...arguments);
        if (!this.kioskMode) {
            return;
        }
        // Contadores reactivos para el menú Debug MF (IndexedDB es asíncrono, así
        // que se cachean y se refrescan tras cada operación).
        this.kioskPendingCount = 0;
        this.kioskFailedCount = 0;

        this._kioskDBReady = new Promise((resolve) => {
            this._kioskDB = new IndexedDB(
                `l10n_ve_kiosk_queue_${this.config.id}`,
                1,
                [
                    ["uuid", PENDING],
                    ["uuid", FAILED],
                ],
                resolve,
                this.dialog
            );
        });
        // Al estar lista la BD: refrescar contadores y reintentar lo pendiente.
        this._kioskDBReady.then(() => {
            this._refreshKioskCounts();
            this.flushKioskRegistrations();
        });

        this._kioskFlushBound = () => this.flushKioskRegistrations();
        browser.addEventListener("online", this._kioskFlushBound);
        const seconds = Number(this.config.auto_sync_interval) || 60;
        this._kioskFlushTimer = browser.setInterval(
            this._kioskFlushBound,
            Math.max(15, seconds) * 1000
        );
    },

    async _kioskReadStore(store) {
        await this._kioskDBReady;
        const data = await this._kioskDB.readAll([store]);
        return (data && data[store]) || [];
    },

    async _refreshKioskCounts() {
        this.kioskPendingCount = (await this._kioskReadStore(PENDING)).length;
        this.kioskFailedCount = (await this._kioskReadStore(FAILED)).length;
    },

    /**
     * Encola un registro fallido. `entry` = {route, order (serializada),
     * access_token, payment_method_id, uuid}. Dedup por `uuid` (keyPath del
     * store: un `put` con el mismo uuid reemplaza, no duplica).
     */
    async enqueueKioskRegistration(entry) {
        if (!entry || !entry.route || !entry.uuid) {
            return;
        }
        await this._kioskDBReady;
        await this._kioskDB.create(PENDING, [{ ...entry, ts: Date.now() }]);
        await this._refreshKioskCounts();
    },

    /**
     * Reintenta todos los pendientes. Ante `ConnectionLostError` se detiene y
     * conserva la cola (servidor aún caído). Un rechazo de negocio NO se
     * descarta: se mueve al store `failed`. Los que entran se eliminan.
     */
    async flushKioskRegistrations() {
        if (this._kioskFlushing) {
            return;
        }
        this._kioskFlushing = true;
        try {
            const queue = await this._kioskReadStore(PENDING);
            for (const entry of queue) {
                try {
                    await rpc(entry.route, {
                        order: entry.order,
                        access_token: entry.access_token,
                        payment_method_id: entry.payment_method_id,
                    });
                } catch (error) {
                    if (error instanceof ConnectionLostError) {
                        break; // servidor aún inaccesible: conservar y reintentar luego
                    }
                    console.error(
                        "[Kiosk sync] el servidor rechazó la orden; se mueve a FALLIDAS",
                        entry.uuid,
                        error
                    );
                    await this._kioskDB.create(FAILED, [
                        {
                            ...entry,
                            errorMessage: String((error && error.message) || error),
                            failedAt: Date.now(),
                        },
                    ]);
                }
                await this._kioskDB.delete(PENDING, [entry.uuid]);
            }
        } finally {
            this._kioskFlushing = false;
            await this._refreshKioskCounts();
        }
    },

    /**
     * Reintenta manualmente las FALLIDAS (tras corregir la causa): las devuelve a
     * `pending` y dispara el flush. Las que sigan fallando vuelven a `failed` con
     * su `errorMessage` actualizado; se devuelven para que la UI (menú Debug MF)
     * muestre el motivo real en vez de un "revisar la causa" genérico.
     */
    async retryFailedKioskRegistrations() {
        const failed = await this._kioskReadStore(FAILED);
        if (!failed.length) {
            return { retried: 0, remaining: [] };
        }
        for (const entry of failed) {
            await this._kioskDB.create(PENDING, [entry]);
            await this._kioskDB.delete(FAILED, [entry.uuid]);
        }
        await this._refreshKioskCounts();
        await this.flushKioskRegistrations();
        const remaining = await this._kioskReadStore(FAILED);
        return { retried: failed.length, remaining };
    },
});
