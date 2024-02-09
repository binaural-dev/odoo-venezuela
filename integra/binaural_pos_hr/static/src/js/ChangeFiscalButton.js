odoo.define('binaural_pos_hr.ChangeFiscalButton', function(require) {
  'use strict';

  const ChangeFiscalButton = require('binaural_pos.ChangeFiscalButton');
  const Registries = require('point_of_sale.Registries');
  const { Gui } = require("point_of_sale.Gui");


  const BinauralHrChangeFiscalButton = (ChangeFiscalButton) =>
    class extends ChangeFiscalButton {
      async onClick() {
        if (!this.env.pos.config.pos_change_receipt_require_supervisor_key) {
          return await super.onClick(...arguments)
        }
        const { confirmed } = await Gui.showPopup("SupervisorPopup", {});
        if (!confirmed) {
          return
        }

        return await super.onClick(...arguments);
      }
    }

  Registries.Component.extend(ChangeFiscalButton, BinauralHrChangeFiscalButton);
  return BinauralHrChangeFiscalButton;
});
