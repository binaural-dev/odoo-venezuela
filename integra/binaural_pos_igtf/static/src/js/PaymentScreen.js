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

      async validateOrder(isForceValidate) {
        let order = this.env.pos.get_order()
        if (order.igtf_amount > 0) {
          let payment_lines = order.get_paymentlines()
          let include = payment_lines.filter(el => el.include_igtf)
          if (include.length == 0) {

            await this.showPopup("ErrorPopup", {
              title: _t("Validation Error"),
              body: _t("You must specify between the payment methods, the tax base and the igtf payment.")
            });
            return false
          }
        }
        return await super.validateOrder(...arguments)
      }
    }

  Registries.Component.extend(PaymentScreen, BinauralPaymentScreen)
  return PaymentScreen
})
