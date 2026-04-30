/** @odoo-module */
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { patch } from "@web/core/utils/patch";
import { onWillUpdateProps } from "@odoo/owl";

// New orders are now associated with the current table, if any.
patch(PaymentScreenStatus.prototype, {
  setup() {
    super.setup(...arguments);
    onWillUpdateProps((nextProps) => {
      nextProps.foreignChangeText
    });
  },
  get foreignRemainingText() {
    const foreignDue = this.props.order.get_foreign_due();
    const due = this

    return this.env.utils.formatForeignCurrency(
      foreignDue > 0 ? foreignDue : 0
    );
  },

  get foreignChangeText() {
    const selectedLine =
      this.props.order.get_order_payment_lines?.()
        .find((line) => line.isSelected()) || null;
    
    return this.env.utils.formatForeignCurrency(
      this.props.order.get_foreign_change(selectedLine)
    );
  },
  
  get currentOrder() {
    return this.props.order
  }
})