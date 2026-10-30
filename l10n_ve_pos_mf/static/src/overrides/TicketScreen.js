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
 */
patch(TicketScreen.prototype, {
    _getFilterOptions() {
        const options = super._getFilterOptions();
        options.set("UNFISCALIZED", { text: _t("Pendientes por facturar") });
        return options;
    },

    async onFilterSelected(selectedFilter) {
        await super.onFilterSelected(...arguments);
        if (this._state.ui.filter === "UNFISCALIZED") {
            await this._fetchSyncedOrders();
        }
    },

    async onSearch(search) {
        await super.onSearch(...arguments);
        if (this._state.ui.filter === "UNFISCALIZED") {
            this._state.syncedOrders.currentPage = 1;
            await this._fetchSyncedOrders();
        }
    },

    getFilteredOrderList() {
        if (this._state.ui.filter === "UNFISCALIZED") {
            return this._state.syncedOrders.toShow;
        }
        return super.getFilteredOrderList();
    },

    _computeSyncedOrdersDomain() {
        const domain = super._computeSyncedOrdersDomain();
        if (this._state.ui.filter === "UNFISCALIZED") {
            domain.push(["mf_invoice_number", "=", false]);
        }
        return domain;
    },

    shouldShowPageControls() {
        if (this._state.ui.filter === "UNFISCALIZED") {
            return this._getLastPage() > 1;
        }
        return super.shouldShowPageControls();
    },

    /**
     * Callback invocado por PrintPendingOrderButton tras imprimir con exito.
     * Invalida el cache del pedido para que la lista de "Pendientes por
     * facturar" deje de mostrarlo en el proximo refetch.
     * @param {number} orderId - backendId (pos.order id) del pedido impreso
     */
    async onOrderFiscalized(orderId) {
        this.pos._invalidateSyncedOrdersCache([orderId]);
        await this._fetchSyncedOrders();
    },
});
