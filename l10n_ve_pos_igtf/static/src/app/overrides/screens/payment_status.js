/** @odoo-module */

import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { usePos } from "@point_of_sale/app/hooks/pos_hook";
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
    return this.env.utils.formatCurrency(this.props.order.get_igtf_amount())
  },
  get biAmount() {
    return this.env.utils.formatCurrency(this.props.order.get_bi_igtf())
  },
  get igtfForeignAmount() {
    return this.env.utils.formatForeignCurrency(this.props.order.get_foreign_igtf_amount())
  },
  get isIgtf() {
    return Array.from(this.props.order.payment_ids || []).some(
      (payment_line) => payment_line.payment_method_id?.apply_igtf
    );
  },
  get suggestedIgtf() {
    // IGTF hipotético si toda la factura se pagara con método apply_igtf.
    // Siempre vía compute_igtf_amount (redondeo de la moneda principal).
    const order = this.props.order;
    const total = Number(order.totalDue ?? 0) || 0;
    return this.env.utils.formatCurrency(order.compute_igtf_amount(total));
  },
  get totalDueTextWithIGTFDisplay() {
    const order = this.props.order;
    const total = Number(order.totalDue ?? 0) || 0;
    return this.env.utils.formatCurrency(
      order._igtfRoundLocal(total + order.compute_igtf_amount(total))
    );
  },
  get totalDueText() {
    return this.env.utils.formatCurrency(this.props.order.get_total_without_igtf())
  },
})
