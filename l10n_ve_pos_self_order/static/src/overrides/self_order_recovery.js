/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { SelfOrder } from "@pos_self_order/app/services/self_order_service";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

/**
 * Recuperación de órdenes del Kiosko (server-side agnóstico a la máquina fiscal).
 *
 * El ciclo de vida de la orden del Kiosko lo gobierna ESTE módulo: aquí se
 * fuerza `to_invoice`, se mantienen los totales foráneos y vive la cola de
 * reintento del registro (`kiosk_sync_queue.js`). La facturación es un paso
 * diferido y reintentable (ver `pos.order._process_saved_order` /
 * `_generate_pos_order_invoice`): si falla al finalizar, la orden queda pagada
 * pendiente de facturar, recuperable desde el panel de órdenes del Kiosko o el
 * menú de backend.
 *
 * Este servicio expone al cliente lo genérico de esa recuperación —listar las
 * órdenes de la sesión y crear la factura de una pendiente— SIN depender de la
 * máquina fiscal. `l10n_ve_pos_mf_self_order` se apoya en lo mismo y le añade
 * encima el estado fiscal y la impresión/reimpresión.
 */
patch(SelfOrder.prototype, {
    /**
     * Órdenes de la sesión gestionables desde el panel del Kiosko
     * (registradas/pagadas, con líneas). Ordenadas de más reciente a más antigua.
     * Las carga del SERVIDOR (`session_orders`) → `connectNewData`, así no
     * dependen de lo que quede en memoria del cliente.
     */
    get kioskSessionOrders() {
        return (this.models["pos.order"] || [])
            .filter(
                (o) =>
                    (o.lines || []).length > 0 &&
                    ["paid", "done", "invoiced"].includes(o.state)
            )
            .sort((a, b) =>
                String(b.date_order || b.id || "").localeCompare(String(a.date_order || a.id || ""))
            );
    },

    /**
     * Crea la factura CONTABLE de una orden del Kiosko que quedó pendiente de
     * facturar (pagada, sin `account_move`). Delega en el endpoint público
     * `create_invoice`, que reusa `action_pos_order_invoice` server-side y es
     * idempotente. Tras esto, la orden queda facturada.
     *
     * @param {Object} order orden del Kiosko (pendiente de facturar)
     * @returns {Promise<{success:boolean, invoice_id?:number, error?:string}>}
     */
    async createKioskInvoice(order) {
        if (!order || typeof order.id !== "number") {
            return { success: false, error: _t("Invalid order") };
        }
        try {
            const res = await rpc("/l10n_ve_pos_self_order/kiosk/create_invoice", {
                access_token: this.access_token,
                order_id: order.id,
            });
            return res || { success: false, error: _t("No response from server") };
        } catch (error) {
            console.error("[Kiosk] create_invoice falló", error);
            return { success: false, error: String((error && error.message) || error) };
        }
    },
});
