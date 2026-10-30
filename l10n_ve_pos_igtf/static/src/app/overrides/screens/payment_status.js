/** @odoo-module */

import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreenStatus.prototype, {
  setup() {
    super.setup(...arguments);
    this.pos = usePos();
  },
  get igtfPercentage() {
    return this.pos.config.igtf_percentage;
  },
  get igtfAmount() {
    return this.env.utils.formatCurrency(this.props.order.get_igtf_amount());
  },
  get biAmount() {
    return this.env.utils.formatCurrency(this.props.order.get_bi_igtf());
  },
  get igtfForeignAmount() {
    return this.env.utils.formatForeignCurrency(this.props.order.get_foreign_igtf_amount());
  },
  get isIgtf() {
    return (this.props.order.get_paymentlines() || []).some(
      (payment_line) => payment_line.payment_method?.apply_igtf
    );
  },
  get suggestedIgtf() {
    const order = this.props.order;
    const total = order.get_total_without_igtf() || 0;
    return this.env.utils.formatCurrency(order.compute_igtf_amount(total));
  },
  get totalDueTextWithIGTFDisplay() {
    const order = this.props.order;
    const total = order.get_total_without_igtf() || 0;
    const igtf = order.compute_igtf_amount(total);
    return this.env.utils.formatCurrency(
      (typeof order._igtfRoundLocal === "function" ? order._igtfRoundLocal(total + igtf) : total + igtf)
    );
  },
  get totalDueText() {
    return this.env.utils.formatCurrency(this.props.order.get_total_without_igtf());
  },
})
