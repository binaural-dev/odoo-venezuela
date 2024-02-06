odoo.define('binaural_pos_hr.TicketScreen', function(require) {
  "use strict";

  const Registries = require('point_of_sale.Registries');
  const TicketScreen = require('point_of_sale.TicketScreen');
  const { Gui } = require("point_of_sale.Gui");
  const { _t } = require("web.core");

  const BinauralTicketScreen = (TicketScreen) =>
    class BinauralTicketScreen extends TicketScreen {
      setup() {
        super.setup();
      }

      async is_valid_supervisor_refund() {

        const { confirmed } = await Gui.showPopup(
          "SupervisorPopup",
          {
            title: _t("Insert Supervisor's Password"),
          }
        );

        return confirmed
      }

      async _onDoRefund() {
        const order = this.getSelectedSyncedOrder();

        if (!order) {
          this._state.ui.highlightHeaderNote = !this._state.ui.highlightHeaderNote;
          return;
        }

        const partner = order.get_partner();

        const allToRefundDetails = this._getRefundableDetails(partner);

        if (allToRefundDetails.length == 0) {
          this._state.ui.highlightHeaderNote = !this._state.ui.highlightHeaderNote;
          return;
        }

        const pos_refund_require_supervisor_key = this.env.pos.config.pos_refund_require_supervisor_key;

        if (pos_refund_require_supervisor_key) {
          const isValid = await this.is_valid_supervisor_refund();

          if (!isValid) return;

        }

        super._onDoRefund()
      }
    };

  Registries.Component.extend(TicketScreen, BinauralTicketScreen);

  return BinauralTicketScreen;

});
