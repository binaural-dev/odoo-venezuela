odoo.define("binaural_pos_hr.PaymentScreen", function (require) {

  const PaymentScreen = require("point_of_sale.PaymentScreen");
  const Registries = require("point_of_sale.Registries");
  const {Gui} = require("point_of_sale.Gui");
  const { _t } = require("web.core");

  const BinauralPaymentScreen = (PaymentScreen) =>
    class BinauralPaymentScreen extends PaymentScreen {
      async toggleIsToInvoice() {

        if (!this.env.pos.config.pos_change_receipt_require_supervisor_key) {
          return await super.toggleIsToInvoice(...arguments)
        }
        const { confirmed } = await Gui.showPopup("SupervisorPopup", {
            title: _t("Insert Supervisor's Password"),
          });
        if (!confirmed) {
          return
        }

        return await super.toggleIsToInvoice(...arguments);
      }
    };

  Registries.Component.extend(PaymentScreen, BinauralPaymentScreen);
  return PaymentScreen;
});
