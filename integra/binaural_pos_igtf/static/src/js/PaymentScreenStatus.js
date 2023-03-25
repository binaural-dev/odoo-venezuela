odoo.define("binaural_pos_igtf.PaymentScreenStatus", function(require) {

  const PaymentScreenStatus = require("point_of_sale.PaymentScreenStatus")
  const Registries = require("point_of_sale.Registries")

  const BinauralPaymentScreenStatus = (PaymentScreenStatus) =>
    class BinauralPaymentScreenStatus extends PaymentScreenStatus {
      get currentOrder() {
        return this.env.pos.get_order();
      }
      get igtfAmount() {
        const posModel = this.env.pos;
        return posModel.format_currency(this.currentOrder.get_igtf_amount(), 'Product Price')
      }
      get isIgtf() {
        let payment_lines = this.currentOrder.get_paymentlines();
        let is_igtf = false;
        payment_lines.forEach(function(payment_line) {
          if (payment_line.payment_method.apply_igtf) {
            is_igtf = true;
          }
        })
        return is_igtf;
      }
    }

  Registries.Component.extend(PaymentScreenStatus, BinauralPaymentScreenStatus)
  return PaymentScreenStatus
})
