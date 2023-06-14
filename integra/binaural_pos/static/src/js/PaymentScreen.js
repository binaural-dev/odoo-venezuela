odoo.define("binaural_pos.PaymentScreen", function(require) {

  const PaymentScreen = require("point_of_sale.PaymentScreen")
  const Registries = require("point_of_sale.Registries")
  const NumberBuffer = require('point_of_sale.NumberBuffer');

  const BinauralPaymentScreen = (PaymentScreen) =>
    class BinauralPaymentScreen extends PaymentScreen {
      _updateSelectedPaymentline() {
        if (!this.selectedPaymentLine) return; // do nothing if no selected payment line

        if (!this.selectedPaymentLine.payment_method.is_foreign_currency) {
          let res = super._updateSelectedPaymentline()
          if(!!this.selectedPaymentLine){
            this.selectedPaymentLine
              .set_foreign_amount(NumberBuffer.getFloat() * this.env.pos.config.foreign_rate)
          }
          return res
        }

        if (NumberBuffer.get() === null) {
          this.deletePaymentLine({ detail: { cid: this.selectedPaymentLine.cid } });
        } else {
          this.selectedPaymentLine.set_foreign_amount(NumberBuffer.getFloat())
          this.selectedPaymentLine.set_amount(
            NumberBuffer.getFloat() * this.env.pos.foreign_currency["inverse_rate"]
          );
        }
      }
      toggleIsToInvoice() {
        // click_invoice
        this.currentOrder.toggle_receipt_invoice(!this.currentOrder.is_to_receipt());
        this.render(true);
      }
    }

  Registries.Component.extend(PaymentScreen, BinauralPaymentScreen)
  return PaymentScreen
})
