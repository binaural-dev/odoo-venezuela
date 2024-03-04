/** @odoo-module **/

import CashMoveButton from 'point_of_sale.CashMoveButton';
import Registries from 'point_of_sale.Registries';

const BinauralCashMoveButton = (CashMoveButton) => 
  class BinauralCashMoveButton extends CashMoveButton {
    async onClick(){
      this.env.pos.open_cashbox();
      return await super.onClick(...arguments)
    }

  }

Registries.Component.extend(CashMoveButton, BinauralCashMoveButton);
return BinauralCashMoveButton
