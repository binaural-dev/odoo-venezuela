odoo.define("l10n_ve_pos_igtf.PaymentScreenStatus", function(require) {

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
      get biAmount(){
        const posModel = this.env.pos;
        return posModel.format_currency(this.currentOrder.get_bi_igtf(), 'Product Price')
      }
      get igtfForeignAmount() {
        const posModel = this.env.pos;
        return posModel.format_foreign_currency(this.currentOrder.get_foreign_igtf_amount(), 'Product Price')
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
      get foreignAmountIGTF(){
        return this.env.pos.format_currency(
          (this.props.order.get_total_with_tax() * (this.env.pos.config.igtf_percentage / 100)) + this.props.order.get_rounding_applied()
        );
      }
      get foreignTotalDueTextWithIGTF() {
        return this.env.pos.format_foreign_currency(
          (this.props.order.get_foreign_total_with_tax() * ((this.env.pos.config.igtf_percentage / 100) + 1)) + this.props.order.get_foreign_rounding_applied()
        );
      }
      get totalDueTextWithIGTF() {
        return this.env.pos.format_currency(
          (this.props.order.get_total_with_tax() * ((this.env.pos.config.igtf_percentage / 100) + 1)) + this.props.order.get_rounding_applied()
        );
      }
    }

  Registries.Component.extend(PaymentScreenStatus, BinauralPaymentScreenStatus)
  return PaymentScreenStatus
})
