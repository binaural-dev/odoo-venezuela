odoo.define('binaural_pos_hr.HeaderButton', function(require) {
  'use strict';

  const HeaderButton = require('point_of_sale.HeaderButton');
  const Registries = require('point_of_sale.Registries');
  const { Gui } = require("point_of_sale.Gui");
  const { _t } = require("web.core");

  const BinauralHeaderButton = (HeaderButton) =>
    class extends HeaderButton {
      async onClick() {
        if (
          this.env.pos.config.pos_type_close_require_supervisor_key != 'button'
          || !this.env.pos.config.pos_close_session_require_supervisor_key) {
          return await super.onClick(...arguments)
        }
        const { confirmed } = await Gui.showPopup("SupervisorPopup",{
            title: _t("Insert Supervisor's Password"),
          });
        if (confirmed) {
          return await super.onClick(...arguments)
        }
      }
    }

  Registries.Component.extend(HeaderButton, BinauralHeaderButton);

  return HeaderButton;
});
