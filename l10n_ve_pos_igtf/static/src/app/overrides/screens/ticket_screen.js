/**
 * PatchScreen - POS Ticket Screen Override
 * This is a basic class template for overriding the POS ticket screen.
 */

import { registry } from '@web/core/registry';
import { patch } from "@web/core/utils/patch";

import { TicketScreen } from '@point_of_sale/app/screens/ticket_screen/ticket_screen';
patch(TicketScreen.prototype, {

    setSelectedOrderGlobal(order) {
        this.pos.selectedOrderData = order; // Guarda toda la orden o solo la propiedad que necesitas
    },

    onClickOrder(clickedOrder) {
        this.setSelectedOrderGlobal(clickedOrder);
        // Llama al método original para mantener la funcionalidad base
        super.onClickOrder(...arguments);
    }
});

