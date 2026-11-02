/** @odoo-module */

import { Component, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

/**
 * Panel de órdenes del Kiosko (estilo TicketScreen del POS): a la izquierda la
 * lista de órdenes de la sesión; al seleccionar una, a la derecha su resumen
 * (cliente, líneas, total, estado) y la acción disponible según su estado.
 *
 * Base (sin máquina fiscal): dos estados —`pending_invoice` (pagada sin factura
 * contable) y `invoiced`— y una sola acción, CREAR FACTURA para la pendiente.
 * `l10n_ve_pos_mf_self_order` extiende este mismo componente y plantilla (patch
 * + t-inherit) para añadir el estado fiscal (`pending_fiscal`/`complete`) y los
 * botones de IMPRIMIR / REIMPRIMIR la copia.
 *
 * Se abre desde el panel de Debug del Kiosko (`KioskDebugDialog`).
 */
export class KioskOrdersDialog extends Component {
    static components = { Dialog };
    static template = "l10n_ve_pos_self_order.KioskOrdersDialog";
    static props = { close: Function };

    setup() {
        this.selfOrder = useService("self_order");
        this.state = useState({ selectedUuid: null, busy: false, message: "", loading: true });
        // Cargar del SERVIDOR las órdenes de la sesión (persistencia real: no
        // dependen de lo que quede en memoria del cliente, que se pierde al
        // iniciar una orden nueva o recargar). connectNewData las mete al modelo.
        onWillStart(() => this.loadOrders());
    }

    async loadOrders() {
        this.state.loading = true;
        try {
            const data = await rpc("/l10n_ve_pos_self_order/kiosk/session_orders", {
                access_token: this.selfOrder.access_token,
            });
            if (data && Object.keys(data).length) {
                this.selfOrder.models.connectNewData(data);
            }
        } catch (error) {
            console.error("[Kiosk] no se pudieron cargar las órdenes de la sesión", error);
            this.state.message = _t("Could not load orders from the server.");
        } finally {
            this.state.loading = false;
        }
    }

    get dialogTitle() {
        return _t("Kiosk Orders");
    }

    get orders() {
        return this.selfOrder.kioskSessionOrders || [];
    }

    get selected() {
        return this.orders.find((o) => o.uuid === this.state.selectedUuid) || null;
    }

    selectOrder(order) {
        this.state.selectedUuid = order.uuid;
        this.state.message = "";
    }

    money(amount) {
        return this.selfOrder.formatMonetary(Number(amount) || 0);
    }

    orderLabel(order) {
        return order.pos_reference || order.tracking_number || order.uuid;
    }

    /**
     * Estado de recuperación de la orden (base, sin máquina fiscal):
     *  - "pending_invoice": pagada pero sin factura contable. Acción: Crear factura.
     *  - "invoiced": ya tiene factura contable.
     * `state === "invoiced"` es la señal AUTORITATIVA del servidor (más fiable que
     * un flag client-side, que puede no venir en órdenes cargadas del server).
     * El módulo fiscal sobreescribe esto para distinguir `pending_fiscal`/`complete`.
     */
    orderStatus(order) {
        if (!order) {
            return "none";
        }
        if (order.state === "invoiced" || order.is_invoiced) {
            return "invoiced";
        }
        return "pending_invoice";
    }

    /** Pago de la orden (genérico: el primero). El módulo fiscal lo refina. */
    get selectedPayment() {
        const order = this.selected;
        if (!order) {
            return null;
        }
        const payments = order.payment_ids || [];
        return payments[0] || null;
    }

    /**
     * Crea la factura contable de la orden pendiente (delega en el servicio
     * `createKioskInvoice`), luego recarga para reflejar el nuevo estado.
     */
    async onCreateInvoice() {
        const order = this.selected;
        if (!order || this.state.busy) {
            return;
        }
        this.state.busy = true;
        this.state.message = _t("Creating the invoice…");
        try {
            const res = await this.selfOrder.createKioskInvoice(order);
            if (res && res.success) {
                this.state.message = res.already_invoiced
                    ? _t("The order was already invoiced.")
                    : _t("Invoice created.");
                await this.loadOrders();
            } else {
                this.state.message = _t(
                    "Could not create the invoice: %s",
                    (res && res.error) || "error"
                );
            }
        } catch (error) {
            this.state.message = _t("Error: %s", String((error && error.message) || error));
        } finally {
            this.state.busy = false;
        }
    }
}
