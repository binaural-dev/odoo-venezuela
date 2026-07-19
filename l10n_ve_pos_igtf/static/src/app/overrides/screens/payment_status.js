/** @odoo-module */

import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreenStatus.prototype, {
  get igtfAmount() {
    return this.env.utils.formatCurrency(this.props.order.get_igtf_amount())
  },
  get biAmount() {
    return this.env.utils.formatCurrency(this.props.order.get_bi_igtf())
  },
  get igtfForeignAmount() {
    return this.env.utils.formatForeignCurrency(this.props.order.get_foreign_igtf_amount())
  },
  get totalWithIgtfAmount() {
    return this.env.utils.formatCurrency(this.props.order.get_total_with_igtf())
  },
  get isIgtf() {
    return Array.from(this.props.order.payment_ids || []).some(
      (payment_line) => payment_line.payment_method_id?.apply_igtf
    );
  },
})
