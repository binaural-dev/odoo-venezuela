/** @odoo-module */
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { patch } from "@web/core/utils/patch";
// New orders are now associated with the current table, if any.
patch(PaymentScreenStatus.prototype, {
  // },
  // get foreignRemainingText() {
  //   return this.env.utils.formatForeignCurrency(
  //     this.props.order.get_foreign_due() > 0 ? this.props.order.get_foreign_due() : 0
  //   );
  // },
  // get foreignChangeText() {
  //   let payment_lines = this.props.order.get_paymentlines();
  //   return this.env.utils.formatForeignCurrency(
  //     this.props.order.get_foreign_change(payment_lines)
  //   );
  // },
  // get currentOrder() {
  //   return this.props.order
  // }
})