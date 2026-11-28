import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreenStatus.prototype, {
  get igtfAmount() {
    return this.pos.formatCurrency(this.props.order.get_igtf_amount());
  },
  get biAmount() {
    return this.pos.formatCurrency(this.props.order.get_bi_igtf());
  },
  get igtfForeignAmount() {
    return this.pos.formatForeignCurrency(this.props.order.get_foreign_igtf_amount());
  },
  get totalWithIgtfAmount() {
    return this.pos.formatCurrency(this.props.order.get_total_with_igtf());
  },
  get foreignTotalWithIgtfAmount() {
    return this.pos.formatForeignCurrency(this.props.order.get_foreign_total_with_igtf());
  },
  get isIgtf() {
    const order = this.props.order;
    return (
      Array.from(order.payment_ids || []).some((payment_line) => payment_line.appliesIgtf) ||
      Boolean(order.hasRefundIgtf?.())
    );
  },
});
