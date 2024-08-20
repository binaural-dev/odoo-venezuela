/** @odoo-module **/

import Registries from 'point_of_sale.Registries';
import TicketScreen from 'point_of_sale.TicketScreen';

const BinauralTicketScreen = (TicketScreen) =>
  class BinauralTicketScreen extends TicketScreen {

    async _onDoRefund() {
      const order = this.getSelectedSyncedOrder();
      if (order.commission_payment_state !== "not_paid") {
        return await this.showPopup('ErrorPopup', {
          title: "Error",
          body: "No se puede aplicar Reembolso a una factura con Estado de Pago (Comisión) En Proceso o Pagada, aplique NC desde Contabilidad; en casos contrarios las NC deben realizarse desde Contabilidad."
        });
      }
      return await super._onDoRefund();
    }
  };

Registries.Component.extend(TicketScreen, BinauralTicketScreen);

return BinauralTicketScreen;

