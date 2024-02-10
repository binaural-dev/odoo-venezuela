odoo.define("binaural_pos_hr.OrderlineState", function(require) {
  "use strict";

  const { Orderline } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");
  const { Gui } = require("point_of_sale.Gui");

  const BinauralOrderlineState = (Orderline) =>
    class BinauralOrderlineState extends Orderline {
      async set_quantity(quantity, keep_price){
        if (!this.pos.config.pos_remove_orderline_require_supervisor_key) {
          return await super.set_quantity(...arguments)
        }
        if (quantity < 1 && quantity > 0 || quantity < 0 && quantity > -1) {
          return await super.set_quantity(...arguments)
        }
        if(quantity === 'remove'){
          const { confirmed } = await Gui.showPopup("SupervisorPopup", {});
          if (!confirmed) {
            return 
          }
        }
        if (quantity < this.quantity) {
          const { confirmed } = await Gui.showPopup("SupervisorPopup", {});
          if (!confirmed) {
            return 
          }
        }
        return await super.set_quantity(...arguments)
      }
    };
  Registries.Model.extend(Orderline, BinauralOrderlineState);
  return BinauralOrderlineState;
})
