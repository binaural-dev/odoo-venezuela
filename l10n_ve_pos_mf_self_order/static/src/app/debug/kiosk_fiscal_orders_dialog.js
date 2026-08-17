/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { Dialog } from "@web/core/dialog/dialog";
import { useService } from "@web/core/utils/hooks";
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
        this.state = useState({ selectedUuid: null, busy: false, message: "" });
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
        return (Number(amount) || 0).toFixed(2);
    }

    orderLabel(order) {
        return order.pos_reference || order.tracking_number || order.uuid;
    }

    async onPrint() {
        const order = this.selected;
        if (!order || this.state.busy) {
            return;
        }
        const isCopy = Boolean(order.mf_invoice_number);
        this.state.busy = true;
        this.state.message = _t("Enviando a la máquina fiscal…");
        try {
            const result = await this.selfOrder.printOrReprintKioskOrder(order);
            if (result && result.valid) {
                this.state.message = isCopy
                    ? _t("Copia reimpresa.")
                    : _t("Factura impresa (nº %s).", order.mf_invoice_number || "");
            } else {
                this.state.message = _t("Falló: %s", (result && result.message) || "error");
            }
        } catch (error) {
            this.state.message = _t("Error: %s", String((error && error.message) || error));
        } finally {
            this.state.busy = false;
        }
    }
}
