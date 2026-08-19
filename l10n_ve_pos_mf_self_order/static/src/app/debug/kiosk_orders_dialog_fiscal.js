/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { KioskOrdersDialog } from "@l10n_ve_pos_self_order/app/debug/kiosk_orders_dialog";

/**
 * Extensión fiscal del panel de órdenes del Kiosko (`KioskOrdersDialog`, base).
 *
 * Añade encima de lo genérico (listar + crear factura) los dos estados fiscales
 * y la acción de máquina fiscal:
 *  - `pending_fiscal`: facturada pero sin número fiscal → botón IMPRIMIR.
 *  - `complete`: ya tiene número fiscal → botón REIMPRIMIR la copia.
 * Los badges, la línea de estado, el detalle del pago verificado (Megasoft) y
 * los botones se inyectan por `t-inherit` (kiosk_orders_dialog_fiscal.xml); aquí
 * va la lógica (estado, pago verificado, impresión).
 */
patch(KioskOrdersDialog.prototype, {
    /**
     * Estado de recuperación en tres niveles (sobreescribe el base de dos):
     *  - "complete": ya tiene número fiscal. Acción: Reimprimir copia.
     *  - "pending_fiscal": facturada, sin número fiscal. Acción: Imprimir.
     *  - "pending_invoice": pagada sin factura contable. Acción: Crear factura.
     */
    orderStatus(order) {
        if (!order) {
            return "none";
        }
        if (order.mf_invoice_number) {
            return "complete";
        }
        if (order.state === "invoiced" || order.is_invoiced) {
            return "pending_fiscal";
        }
        return "pending_invoice";
    },

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
    },

    /**
     * Imprime (si aún no tiene número fiscal) o reimprime la COPIA (si ya lo
     * tiene) en la máquina fiscal, vía el servicio `self_order`.
     */
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
    },
});
