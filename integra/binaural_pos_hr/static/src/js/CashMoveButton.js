/** @odoo-module **/

import CashMoveButton from 'point_of_sale.CashMoveButton';
import Registries from 'point_of_sale.Registries';
import { Gui } from "point_of_sale.Gui";

const BinauralCashMoveButton = (CashMoveButton) =>
  class BinauralCashMoveButton extends CashMoveButton {
    async onClick() {
      if (!this.env.pos.config.pos_cashmove_require_supervisor_key) {
        return await super.onClick(...arguments)
      }
      const { confirmed } = await Gui.showPopup(
        "SupervisorPopup",{}
      );
      if (!confirmed) {
        return
      }
      return await super.onClick(...arguments)
    }


  }

Registries.Component.extend(CashMoveButton, BinauralCashMoveButton);
return BinauralCashMoveButton
