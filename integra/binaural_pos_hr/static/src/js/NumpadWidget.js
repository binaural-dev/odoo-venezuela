odoo.define("binaural_pos_hr.NumpadWidget", function (require) {
  "use strict";

  const NumpadWidget = require("point_of_sale.NumpadWidget");
  const Registries = require("point_of_sale.Registries");

  const { Gui } = require("point_of_sale.Gui");
  const { _t } = require("web.core");

  const BinauralNumpadWidget = (NumpadWidget) =>
    class extends NumpadWidget {
      async setup() {
        super.setup()
      }

      async is_valid_supervisor_discount() {
        const { confirmed } = await Gui.showPopup(
          "SupervisorPopup",
          {
            title: _t("Insert Supervisor's Password"),
          }
        );

        return confirmed
      }

      async changeMode(mode) {

        if (mode == 'discount' && this.env.pos.numpadMode != 'discount') {
          const pos_require_supervisor_key = this.env.pos.config.pos_require_supervisor_key;
          
          if (pos_require_supervisor_key) {
            const is_valid_discount = await this.is_valid_supervisor_discount();
            if (!is_valid_discount) return;

          }

        }

        super.changeMode(mode);

      }
    };

  Registries.Component.extend(NumpadWidget, BinauralNumpadWidget);
  return NumpadWidget;
});
