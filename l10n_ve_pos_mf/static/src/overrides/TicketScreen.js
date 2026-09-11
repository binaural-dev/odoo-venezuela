/** @odoo-module **/

import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ReprintInvoiceButton } from "../js/ReprintInvoiceButton";
import { PrintPendingOrderButton } from "../components/PrintPendingOrderButton/PrintPendingOrderButton";

patch(TicketScreen, {
    components: {
        ...TicketScreen.components,
        ReprintInvoiceButton,
        PrintPendingOrderButton,
    },
});

/**
 * Filtro adicional "Pendientes por facturar": reutiliza el mecanismo de
 * ordenes sincronizadas (SYNCED) del TicketScreen base, agregando la
 * condicion mf_invoice_number = False al dominio de busqueda en backend.
 * Permite ubicar rapidamente los pedidos que quedaron sin imprimir en la
 * maquina fiscal, por ejemplo cuando el cierre de sesion se bloquea por
 * pedidos sin facturar (ver ClosePosPopup.closeSessionAndPrintZ).
 *
 * Migración 17 → 19: this._state.ui.filter → this.state.filter; el cache
 * de órdenes sincronizadas ahora vive en los modelos del POS
 * (pos.models["pos.order"]) y se refresca con pos.data.loadServerOrders.
 */
patch(TicketScreen.prototype, {
    _getFilterOptions() {
        const options = super._getFilterOptions();
        options.set("UNFISCALIZED", { text: _t("Pendientes por facturar") });
        return options;
    },

    async onFilterSelected(selectedFilter) {
        await super.onFilterSelected(...arguments);
        if (this.state.filter === "UNFISCALIZED") {
            await this._fetchSyncedOrders();
        }
    },

    async onSearch(search) {
        await super.onSearch(...arguments);
        if (this.state.filter === "UNFISCALIZED") {
            this.pos.screenState.ticketSCreen.offsetByDomain = {};
            await this._fetchSyncedOrders();
        }
    },

    _computeSyncedOrdersDomain() {
        const domain = super._computeSyncedOrdersDomain();
        if (this.state.filter === "UNFISCALIZED") {
            return [...domain, ["mf_invoice_number", "=", false]];
        }
        return domain;
    },

    getFilteredOrderList() {
        if (this.state.filter === "UNFISCALIZED") {
            const orderModel = this.pos.models["pos.order"];
            const orders = orderModel
                .filter((o) => o.finalized && !o.mf_invoice_number)
                .sort((a, b) => b.date_order - a.date_order);
            return orders.slice(
                (this.state.page - 1) * this.state.nbrByPage,
                this.state.page * this.state.nbrByPage
            );
        }
        return super.getFilteredOrderList();
    },

    /**
     * Callback invocado por PrintPendingOrderButton tras imprimir con exito.
     * Recarga el pedido desde el backend para que la lista de "Pendientes
     * por facturar" deje de mostrarlo.
     * @param {number} orderId - id backend (pos.order) del pedido impreso
     */
    async onOrderFiscalized(orderId) {
        if (orderId) {
            await this.pos.data.loadServerOrders([["id", "=", orderId]]);
        }
        await this._fetchSyncedOrders();
    },
});
