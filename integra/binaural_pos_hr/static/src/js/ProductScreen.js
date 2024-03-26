odoo.define('binaural_pos_hr.ProductScreen', function(require) {
  "use strict";

  const Registries = require('point_of_sale.Registries');
  const ProductScreen = require('point_of_sale.ProductScreen');
  const NumberBuffer = require('point_of_sale.NumberBuffer');
  const { _t } = require('web.core');
  const { Gui } = require("point_of_sale.Gui");

  const BinauralHrProductScreen = (ProductScreen) =>
    class BinauralHrProductScreen extends ProductScreen {
      _setValue(val) {
        const order = this.env.pos.get_order();
        const selectedLine = order.get_selected_orderline();
        if (this.env.pos.numpadMode === 'quantity' && val === "" && selectedLine.get_quantity() === 0) {
          super._setValue("remove")
        } else {
          return super._setValue(...arguments)
        }
      }
      async _updateSelectedOrderline(event) {
        if (!this.env.pos.config.pos_remove_orderline_require_supervisor_key) {
          await super._updateSelectedOrderline(...arguments)
        }
        const order = this.env.pos.get_order();
        const selectedLine = order.get_selected_orderline();
        if (!selectedLine) {
          await super._updateSelectedOrderline(...arguments)
        }

        let keys = ["Backspace","+", "-"]

        if (this.env.pos.numpadMode === 'quantity' && keys.includes(event.detail.key) && this.env.pos.config.pos_remove_orderline_require_supervisor_key) {
          const { confirmed } = await this.showPopup("SupervisorPopup", {
            title: _t("Insert Supervisor's Password"),
          });
          if (!confirmed) {
            return
          }
        }

        await super._updateSelectedOrderline(...arguments)
      }
    };

  Registries.Component.extend(ProductScreen, BinauralHrProductScreen);

  return BinauralHrProductScreen;

});
