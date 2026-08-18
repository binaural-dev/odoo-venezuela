/** @odoo-module */

import { Component, useState, onWillStart } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

/**
 * Panel de órdenes fiscales del Kiosko (estilo TicketScreen del POS): a la
 * izquierda la lista de órdenes de la sesión; al seleccionar una, a la derecha
 * su resumen (cliente, líneas, total, estado fiscal) y un botón para
 * IMPRIMIR (si aún no tiene número fiscal) o REIMPRIMIR la COPIA (si ya lo tiene).
 *
 * Se abre desde el menú Debug MF. La lógica fiscal vive en el servicio
 * `self_order` (`printOrReprintKioskOrder` / `kioskFiscalOrders`).
 */
export class KioskFiscalOrdersDialog extends Component {
    static components = { Dialog };
    static template = "l10n_ve_pos_mf_self_order.KioskFiscalOrdersDialog";
    static props = { close: Function };

    setup() {
        this.selfOrder = useService("self_order");
        this.state = useState({ selectedUuid: null, busy: false, message: "", loading: true });
        // Cargar del SERVIDOR las órdenes de la sesión (persistencia real: no
        // dependen de lo que quede en memoria del cliente, que se pierde al
        // iniciar una orden nueva o recargar). connectNewData las mete al modelo
        // para que el builder fiscal client-side las use tal cual.
        onWillStart(() => this.loadOrders());
    }

    async loadOrders() {
        this.state.loading = true;
        try {
            const data = await rpc("/l10n_ve_pos_mf_self_order/kiosk/session_orders", {
                access_token: this.selfOrder.access_token,
            });
            if (data && Object.keys(data).length) {
                this.selfOrder.models.connectNewData(data);
            }
        } catch (error) {
            console.error("[MF Kiosk] no se pudieron cargar las órdenes de la sesión", error);
            this.state.message = _t("Could not load orders from the server.");
        } finally {
            this.state.loading = false;
        }
    }

    get dialogTitle() {
        return _t("Kiosk Fiscal Orders");
    }

    get orders() {
        return this.selfOrder.kioskFiscalOrders || [];
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
     * Estado de recuperación de la orden, en tres niveles:
     *  - "pending_invoice": pagada pero sin factura contable (`account_move`).
     *    Acción: Crear factura.
     *  - "pending_fiscal": facturada pero sin número fiscal. Acción: Imprimir.
     *  - "complete": ya tiene número fiscal. Acción: Reimprimir copia.
     */
    orderStatus(order) {
        if (!order) {
            return "none";
        }
        if (order.mf_invoice_number) {
            return "complete";
        }
        if (order.is_invoiced) {
            return "pending_fiscal";
        }
        return "pending_invoice";
    }

    /** Pago verificado de la orden (Megasoft): el que traiga datos del VPOS. */
    get selectedPayment() {
        const order = this.selected;
        if (!order) {
            return null;
        }
        const payments = order.payment_ids || [];
        return (
            payments.find((p) => p.megasoft_auth || p.megasoft_reference) ||
            payments[0] ||
            null
        );
    }

    /**
     * Crea la factura contable de la orden pendiente (delega en el endpoint de
     * `l10n_ve_pos_self_order`), luego recarga para reflejar el nuevo estado (que
     * habilita la impresión fiscal).
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
                    : _t("Invoice created. It can now be printed on the fiscal machine.");
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

    async onPrint() {
        const order = this.selected;
        if (!order || this.state.busy) {
            return;
        }
        const isCopy = Boolean(order.mf_invoice_number);
        this.state.busy = true;
        this.state.message = _t("Sending to the fiscal machine…");
        try {
            const result = await this.selfOrder.printOrReprintKioskOrder(order);
            if (result && result.valid) {
                this.state.message = isCopy
                    ? _t("Copy reprinted.")
                    : _t("Invoice printed (no. %s).", order.mf_invoice_number || "");
            } else {
                this.state.message = _t("Failed: %s", (result && result.message) || "error");
            }
        } catch (error) {
            this.state.message = _t("Error: %s", String((error && error.message) || error));
        } finally {
            this.state.busy = false;
        }
    }
}
