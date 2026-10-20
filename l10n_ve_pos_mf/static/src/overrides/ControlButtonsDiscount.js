/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ControlButtons } from "@point_of_sale/app/screens/product_screen/control_buttons/control_buttons";

patch(ControlButtons.prototype, {
  async applyDiscount(percent) {
    this.pos._mf_manual_discount_trigger = true;
    try {
      return await super.applyDiscount(...arguments);
    } finally {
      this.pos._mf_manual_discount_trigger = false;
    }
  },
});
