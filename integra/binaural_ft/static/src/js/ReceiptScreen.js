/** @odoo-module **/

import ReceiptScreen from "point_of_sale.ReceiptScreen";
import Registries from "point_of_sale.Registries";
import { Gui } from "point_of_sale.Gui";

export const BinauralReceiptScreen = (ReceiptScreen) =>
  class BinauralReceiptScreen extends ReceiptScreen {
    async printTicketInvoice() {
      try {
        if (!this.env.proxy.iot_device_proxies.printer) {
          return Gui.showPopup("ErrorPopup", {
            title: "No se tiene una impresora configurada a la caja",
          });
        }
        let identifier = this.env.proxy.iot_device_proxies.printer._identifier
        let printer_id = this.env.pos.iot_device_by_identifier[identifier].id
        const order = this.currentOrder;
        const orderName = order.get_name();
        const orderId = this.env.pos.validated_orders_name_server_id_map[orderName];
        if (!orderId)  {
          return Gui.showPopup("ErrorPopup", {
            title: "No se ha registrado la factura en Odoo",
          });
        }
        const [orderWithInvoice] = await this.rpc({
          method: 'read',
          model: 'pos.order',
          args: [orderId, ['account_move']],
          kwargs: { load: false },
        });
        if (orderWithInvoice && orderWithInvoice.account_move) {
          await this.env.legacyActionManager.do_action(this.env.pos.reports_mf[printer_id], {
            additional_context: {
              active_ids: [orderWithInvoice.account_move],
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
Registries.Component.extend(ReceiptScreen, BinauralReceiptScreen);
