odoo.define('binaural_pos_hr.ClosePosPopup', function(require) {
  'use strict';

  const ClosePosPopup = require('point_of_sale.ClosePosPopup');
  const Registries = require('point_of_sale.Registries');
  const { Gui } = require("point_of_sale.Gui");
  const { _t } = require("web.core");

  const BinauralClosePosPopup = (ClosePosPopup) =>
    class extends ClosePosPopup {
      async confirm() {
        if (
          this.env.pos.config.pos_type_close_require_supervisor_key  != 'popup'
          || !this.env.pos.config.pos_close_session_require_supervisor_key) {
          return await super.confirm()
        }
        const { confirmed } = await Gui.showPopup("SupervisorPopup",{
            title: _t("Insert Supervisor's Password"),
          });
        if (confirmed) {
          return await super.confirm()
        }
      }
    }

  Registries.Component.extend(ClosePosPopup, BinauralClosePosPopup);

  return ClosePosPopup;
});
