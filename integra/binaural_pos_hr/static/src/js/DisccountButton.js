odoo.define('binaural_pos_hr.DiscountButton', function(require) {
  'use strict';

  const DiscountButton = require('binaural_pos_discount.DiscountButton');
  const Registries = require('point_of_sale.Registries');
  const { Gui } = require("point_of_sale.Gui");
  const { _t } = require("web.core");

  const BinauralDiscountButton = (DiscountButton) =>
    class extends DiscountButton {

      async is_valid_supervisor_discount() {

        const { confirmed } = await Gui.showPopup(
          "SupervisorPopup",
          {
            title: _t("Insert Supervisor's Password"),
          }
        );

        return confirmed
      }

      async onClick() {
        var self = this;

        const pos_discount_require_supervisor_key = this.env.pos.config.pos_discount_require_supervisor_key;

        if (pos_discount_require_supervisor_key) {
          const isValid = await self.is_valid_supervisor_discount();

          if (isValid) {
            await super.onClick();
          }

          return
        }

        await super.onClick();
      }

    }

  Registries.Component.extend(DiscountButton, BinauralDiscountButton);

  return DiscountButton;
});
