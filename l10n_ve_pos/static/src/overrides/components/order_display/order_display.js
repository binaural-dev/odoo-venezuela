/** @odoo-module **/

import { OrderDisplay } from "@point_of_sale/app/components/order_display/order_display";
import { patch } from "@web/core/utils/patch";
import { onWillUpdateProps, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { debounce } from "@web/core/utils/timing";
patch(OrderDisplay, {
  props: {
    ...OrderDisplay.props,
    conversion_rate: { optional: true },
    foreign_inverse_rate: { optional: true },
    foreign_total_with_taxes: { optional: true },
    foreign_total_tax: { optional: true },
    foreign_tax_total: { optional: true },
    quantity_products: { optional: true },
    foreignTotalWithTaxes: { optional: true },
  },
});

patch(OrderDisplay.prototype, {
  setup() {
    super.setup(...arguments);
    this._lastReqId = 0;
    this.orm = useService("orm");
    this.state = useState({ foreignTotalOrderDisplay: 0 });

    const debouncedSync = debounce(async (amount) => {
      await this._syncForeignAmountDisplay(amount);
    }, 300);

    onWillStart(async () => {
      await this._syncForeignAmountDisplay(this.props.order.get_total_with_tax());
    });

    onWillUpdateProps((nextProps) => {
      debouncedSync(nextProps.order.get_total_with_tax());
    });
  },

  get foreignTotalWithTaxes() {
    return this.state.foreignTotalOrderDisplay;
  },

  //converts amount
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
        return this.state.foreignTotalOrderDisplay = converted;
      }
    } catch (err) {
      console.log("Error converting total amount:", err);
      if (reqId === this._lastReqId) {
        const rate = Number(this.pos?.foreing_rate || 1);
        return this.state.foreignTotalOrderDisplay = amount * rate;
      }
    }
  },
});



