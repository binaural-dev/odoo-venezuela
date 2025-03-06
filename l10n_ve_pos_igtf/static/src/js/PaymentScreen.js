odoo.define("l10n_ve_pos_igtf.PaymentScreen", function(require) {

  const PaymentScreen = require("point_of_sale.PaymentScreen")
  const Registries = require("point_of_sale.Registries")
  const NumberBuffer = require('point_of_sale.NumberBuffer');
  const { _t } = require('web.core');
  const { onMounted } = owl;

  const BinauralPaymentScreen = (PaymentScreen) =>
    class BinauralPaymentScreen extends PaymentScreen {
      _updateSelectedPaymentline() {
        super._updateSelectedPaymentline()
        this.currentOrder.update_igtf();
        this.render();
      }
      setup() {
        super.setup();
        onMounted(this.onMounted);
      }
      onMounted() {
        this.currentOrder.update_igtf();
      }
      toggleIsToInvoice() {
        super.toggleIsToInvoice()
        this.currentOrder.update_igtf();
        this.render();
      }
    }

  Registries.Component.extend(PaymentScreen, BinauralPaymentScreen)
  return PaymentScreen
})
