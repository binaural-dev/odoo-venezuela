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
 * Odoo 20: el core solo trae del servidor las ordenes de los filtros
 * SYNCED y CANCELLED (`_updateSyncedOrders`), asi que el filtro hace la misma
 * consulta (`search_order_ids` en estado pagado) con su dominio extra.
 */
patch(TicketScreen.prototype, {
    _getFilterOptions() {
        const options = super._getFilterOptions();
        options.set("UNFISCALIZED", { text: _t("Pendientes por facturar") });
        return options;
    },

    _computeSyncedOrdersDomain() {
        const domain = super._computeSyncedOrdersDomain();
        if (this.state.filter === "UNFISCALIZED") {
            return [...domain, ["mf_invoice_number", "=", false]];
        }
        return domain;
    },

    async _updateSyncedOrders() {
        if (this.state.filter !== "UNFISCALIZED") {
            return super._updateSyncedOrders(...arguments);
        }
        const screenState = this.pos.screenState.ticketScreen;
        const domain = this._computeSyncedOrdersDomain();
        const key = JSON.stringify(domain);
        const { ordersInfo, totalCount } = await this.pos.data.call(
            "pos.order",
            "search_order_ids",
            [],
            {
                config_id: this.pos.config.id,
                domain,
                limit: this.state.nbrByPage,
                offset: screenState.offsetByDomain[key] || 0,
                state_filter: "paid",
            }
        );
        screenState.offsetByDomain[key] =
            (screenState.offsetByDomain[key] || 0) + ordersInfo.length;
        screenState.totalCount = totalCount;

        const idsToLoad = ordersInfo.map((info) => info[0]);
        if (idsToLoad.length) {
            await this.pos.data.loadServerOrders([["id", "in", idsToLoad]]);
        }
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
});
