/** @odoo-module **/

import TicketScreen from "point_of_sale.TicketScreen";
import Registries from "point_of_sale.Registries";
import { Gui } from "point_of_sale.Gui";

export const BinauralTicketScreen = (TicketScreen) =>
    class BinauralTicketScreen extends TicketScreen{
        async printTicketInvoice() {
            try {
                if (!this.env.proxy.iot_device_proxies.printer) {
                return Gui.showPopup("ErrorPopup", {
                    title: "No se tiene una impresora configurada a la caja",
                });
                }
                let identifier = this.env.proxy.iot_device_proxies.printer._identifier
                let printer_id = this.env.pos.iot_device_by_identifier[identifier].id
                const order = this.getSelectedSyncedOrder();
                if (!order.account_move)  {
                    return Gui.showPopup("ErrorPopup", {
                        title: "No se ha registrado la factura en Odoo",
                    });
                }
                if (order && order.account_move) {
                    await this.env.legacyActionManager.do_action(this.env.pos.reports_mf[printer_id], {
                        additional_context: {
                        active_ids: [order.account_move],
                        },
                    });
                }
            } catch (e) {
                Gui.showPopup("ErrorPopup", {
                title: "Ha ocurrido un error al intentar imprimir",
                });
            }
        }
    }
Registries.Component.extend(TicketScreen, BinauralTicketScreen);
