/** @odoo-module */

import { usePos } from "@point_of_sale/app/store/pos_hook";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { Component } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";

export class ChangeFiscalButton extends Component {
  static template = "l10n_ve_pos.ChangeFiscalButton";
  setup() {
    this.pos = usePos();
  }
  get currentOrder() {
    return this.pos.get_order();
  }
  async onClick() {
    this.currentOrder.toggle_receipt_invoice(!this.currentOrder.is_to_receipt());
    this.render(true);
  }
}

ProductScreen.addControlButton({
  component: ChangeFiscalButton,
  position: ["before", "SetFiscalPositionButton"],
});

