odoo.define("binaural_pos.PaymentScreenStatus", function(require) {

  const PaymentScreenStatus = require("point_of_sale.PaymentScreenStatus")
  const Registries = require("point_of_sale.Registries")

  const BinauralPaymentScreenStatus = (PaymentScreenStatus) =>
    class BinauralPaymentScreenStatus extends PaymentScreenStatus {
        get foreignChangeText() {
            return this.env.pos.format_foreign_currency(this.props.order.get_foreign_change());
        }
        get foreignTotalDueText() {
            return this.env.pos.format_foreign_currency(
                this.props.order.get_foreign_total_with_tax() + this.props.order.get_foreign_rounding_applied()
            );
        }
        get foreignRemainingText() {
            return this.env.pos.format_foreign_currency(
                this.props.order.get_due() > 0 ? this.props.order.get_foreign_due() : 0
            );
        }

    }

  Registries.Component.extend(PaymentScreenStatus, BinauralPaymentScreenStatus)
  return PaymentScreenStatus 
})
