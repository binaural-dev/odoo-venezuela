odoo.define("binaural_pos_hr.ProductScreen", function (require) {
  "use strict";

  const Registries = require("point_of_sale.Registries");
  const ProductScreen = require("point_of_sale.ProductScreen");
  const { parse } = require("web.field_utils");
  const { _t } = require("web.core");

  const BinauralHrProductScreen = (ProductScreen) =>
    class extends ProductScreen {
      async _setValue(inputValue) {
        const order = this.env.pos.get_order();
        const selectedLine = order.get_selected_orderline();
        const currentQuantity = selectedLine.get_quantity();
        const newQuantity = parse.float(inputValue);

        // Supervisor check for removing an item or reducing quantity
        if (
          this.env.pos.numpadMode === "quantity" &&
          ((inputValue === "" && currentQuantity === 0) ||
            newQuantity < currentQuantity)
        ) {
          const confirmed = await this._requireSupervisorApproval();
          if (!confirmed) {
            return super._setValue(currentQuantity);
          }
          if (inputValue === "" && currentQuantity === 0) {
            return super._setValue("remove");
          }
        }

        return super._setValue(...arguments);
      }

      async _requireSupervisorApproval() {
        const { confirmed } = await this.showPopup("SupervisorPopup", {
          title: _t("Insert Supervisor's Password"),
        });
        return confirmed;
      }
    };

  Registries.Component.extend(ProductScreen, BinauralHrProductScreen);

  return BinauralHrProductScreen;
});
