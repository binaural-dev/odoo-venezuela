/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

import { _t } from "@web/core/l10n/translation";

// Flag to store whether the user has the permission to change quantity on POS orders
let userHasGroupChangeQtyOnPosOrder = false;
let userHasGroupChangePriceOnPosOrder = false;

patch(ProductScreen.prototype, {
  setup() {
    super.setup();
    this.user = useService("user");

    // Determine if the current user belongs to the group that can change quantity on POS orders
    onWillStart(async () => {
      userHasGroupChangeQtyOnPosOrder = await this.user.hasGroup(
        "l10n_ve_pos.group_change_qty_on_pos_order",
      );
      userHasGroupChangePriceOnPosOrder = await this.user.hasGroup(
        "l10n_ve_pos.group_change_price_on_pos_order",
      );
    });
  },

  getNumpadButtons() {
    const buttons = super.getNumpadButtons();

    // Disable the quantity button if the user does not belong to the required group
    const quantityButton = buttons.find(
      (button) => button.value === "quantity",
    );
    if (quantityButton && !userHasGroupChangeQtyOnPosOrder) {
      quantityButton.disabled = true;
    }

    // Disable the price button if the user does not belong to the required group
    const priceButton = buttons.find((button) => button.value === "price");
    if (priceButton && !userHasGroupChangePriceOnPosOrder) {
      priceButton.disabled = true;
    }

    return buttons;
  },

  async _canRemoveLine() {
    return Promise.resolve({ auth: true });
  },
  async _setValue(val) {
    const { numpadMode } = this.pos;
    let selectedLine = this.currentOrder.get_selected_orderline();
    if (!selectedLine) {
      this.numberBuffer.reset();
    }
    if (
      !selectedLine &&
      this.currentOrder.get_orderlines().length > 0 &&
      (val == "" || val == "remove")
    ) {
      let orderlines = this.currentOrder.get_orderlines();
      this.currentOrder.select_orderline(orderlines[orderlines.length - 1]);
      return;
    }
    if (selectedLine && numpadMode === "quantity") {
      if (val === "0" || val == "" || val === "remove") {
        const { auth } = await this._canRemoveLine();
        if (!auth) {
          this.numberBuffer.reset();
          this.currentOrder.deselect_orderline();
          return;
        }
        this.numberBuffer.reset();
        this.currentOrder.removeOrderline(selectedLine);
        this.currentOrder.deselect_orderline();
        return;
      }
    }
    return await super._setValue(val);
  },
});
