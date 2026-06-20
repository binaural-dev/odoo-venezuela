/** @odoo-module **/

import { TicketScreen } from "@point_of_sale/app/screens/ticket_screen/ticket_screen";
import { patch } from "@web/core/utils/patch";
import { ReprintInvoiceButton } from "../js/ReprintInvoiceButton";

patch(TicketScreen, {
    components: {
        ...TicketScreen.components,
        ReprintInvoiceButton,
    },
});
