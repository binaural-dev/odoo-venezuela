odoo.define("binaural_pos.PaymentScreen", function(require) {

  const PaymentScreen = require("point_of_sale.PaymentScreen")
  const Registries = require("point_of_sale.Registries")
  const NumberBuffer = require('point_of_sale.NumberBuffer');

  const BinauralPaymentScreen = (PaymentScreen) =>
    class BinauralPaymentScreen extends PaymentScreen {
      _updateSelectedPaymentline() {
        console.log("AQUIS")
        if (!this.selectedPaymentLine) return; // do nothing if no selected payment line

        if (!this.selectedPaymentLine.payment_method.is_foreign_currency) {
          return super._updateSelectedPaymentline()
        }
        console.log("AQUIIIIIIIIIIIIIIIIIIIII")

        this.selectedPaymentLine.set_foreign_amount(NumberBuffer.getFloat())
        this.selectedPaymentLine.set_amount(
          NumberBuffer.getFloat() * this.env.pos.foreign_currency["inverse_rate"] 
        );
      }
    }

  Registries.Component.extend(PaymentScreen, BinauralPaymentScreen)
  return PaymentScreen
})
