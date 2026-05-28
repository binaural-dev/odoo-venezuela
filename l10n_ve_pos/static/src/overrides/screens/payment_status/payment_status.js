/** @odoo-module */
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { patch } from "@web/core/utils/patch";
import { onPatched, onWillUpdateProps, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// New orders are now associated with the current table, if any.
patch(PaymentScreenStatus.prototype, {
  setup() {
    super.setup(...arguments);
    this.orm = useService("orm");
    this._lastReqId = 0;
    this.state = useState({ foreignDueOrderDisplay: 0 });

    onWillStart(async () => {
      await this._syncForeignAmountDisplay(this._getDisplaySourceAmount(this.props.order));
    });

    onWillUpdateProps(async (nextProps) => {
      await this._syncForeignAmountDisplay(this._getDisplaySourceAmount(nextProps.order));
    });

    onPatched(async () => {
      await this._syncForeignAmountDisplay(this._getDisplaySourceAmount(this.props.order));
    });
  },

  _getDisplaySourceAmount(order = this.props.order) {
    if (!order) {
      return 0;
    }
    return order.isRemaining ? order.change : order.remainingDue;
  },

  get foreignDueOrderAmountRound() {
    return this.env.utils.formatForeignCurrency(
      this.state.foreignDueOrderDisplay
    );
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
      this.props.order.get_foreign_due(selectedLine)
    );
  },
  
  get currentOrder() {
    return this.props.order
  },

  async _syncForeignAmountDisplay(amount) {
    if (!Number.isFinite(amount)) {
      return 0;
    }
    const reqId = ++this._lastReqId;
    try {
      const converted = await this.orm.call(
        "pos.order",
        "convert_amount",
        [amount],
        { context: { amount } }
      );
      if (reqId === this._lastReqId) {
        if (this.state.foreignDueOrderDisplay !== converted) {
          this.state.foreignDueOrderDisplay = converted;
        }
        return this.state.foreignDueOrderDisplay;
      }
    } catch (err) {
      console.log("Error converting total amount:", err);
      if (reqId === this._lastReqId) {
        const rate = Number(this.pos?.foreign_rate || 1);
        const fallbackAmount = amount / rate;
        if (this.state.foreignDueOrderDisplay !== fallbackAmount) {
          this.state.foreignDueOrderDisplay = fallbackAmount;
        }
        return this.state.foreignDueOrderDisplay;
      }
    }
  },
})