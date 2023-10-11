/** @odoo-module **/

import ReceiptScreen from "point_of_sale.ReceiptScreen";
import Registries from "point_of_sale.Registries";

// const ReceiptScreenObj = ReceiptScreen();
export const BodegonReceiptScreen = (ReceiptScreen) =>
  class BodegonReceiptScreen extends ReceiptScreen {
    printDeliveryCommand() {
      return this.showScreen("DeliveryCommandScreen", {
        order: this.currentOrder,
        goBack: "ReceiptScreen",
      });
    }
  }
Registries.Component.extend(ReceiptScreen, BodegonReceiptScreen);