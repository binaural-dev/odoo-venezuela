/** @odoo-module */
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { patch } from "@web/core/utils/patch";
// New orders are now associated with the current table, if any.
patch(PaymentScreenStatus.prototype, {
  get foreignTotalDueText() {
    let igtf_payment_methods = this.props.order.get_paymentlines().filter(payment => payment.payment_method.apply_igtf);

    if (igtf_payment_methods.length > 0) {
      return this.env.utils.formatForeignCurrency(
        this.props.order.get_foreign_total_with_tax() + this.props.order.get_foreign_rounding_applied() + this.props.order.get_foreign_igtf_amount()
      );
    } else {
      return this.env.utils.formatForeignCurrency(
        this.props.order.get_foreign_total_with_tax() + this.props.order.get_foreign_rounding_applied()
      );

  }},
  get foreignRemainingText() {
    return this.env.utils.formatForeignCurrency(
      this.props.order.get_foreign_due() > 0 ? this.props.order.get_foreign_due() : 0
    );
  },
  get foreignChangeText() {
    let payment_lines = this.props.order.get_paymentlines();
    return this.env.utils.formatForeignCurrency(
      this.props.order.get_foreign_change(payment_lines)
    );
  },
  get currentOrder(){
    return this.props.order
  }
})