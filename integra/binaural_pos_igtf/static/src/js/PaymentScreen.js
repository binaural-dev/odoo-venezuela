odoo.define("binaural_pos_igtf.PaymentScreen", function(require) {

  const PaymentScreen = require("point_of_sale.PaymentScreen")
  const Registries = require("point_of_sale.Registries")
  const NumberBuffer = require('point_of_sale.NumberBuffer');
  const { _t } = require('web.core');

  const BinauralPaymentScreen = (PaymentScreen) =>
    class BinauralPaymentScreen extends PaymentScreen {
      _updateSelectedPaymentline() {
        super._updateSelectedPaymentline()
        this.currentOrder.update_igtf();
        this.render();
      }
    }

  Registries.Component.extend(PaymentScreen, BinauralPaymentScreen)
  return PaymentScreen
})
