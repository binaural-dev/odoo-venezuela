/** @odoo-module */

import { Payment } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { roundPrecision as round_pr } from "@web/core/utils/numbers";

patch(Payment.prototype, {
  setup(_defaultObj, options) {
    super.setup(...arguments);
    this.igtf_amount = this.igtf_amount || 0;
    this.foreign_igtf_amount = this.foreign_igtf_amount || 0;
  },
  set_include_igtf(value) {
    this.include_igtf = value;
  },
  set_igtf_amount(amount) {
    this.igtf_amount = amount;
  },
  set_foreign_igtf_amount(amount) {
    this.foreign_igtf_amount = amount;
  },
  set_foreign_amount(amount) {
    const order = this.order;
    const method = this.payment_method;
    const hasIgtfContext =
      Boolean(method?.apply_igtf) ||
      (order && (order.igtf_amount || 0) !== 0);
    if (
      order?.to_invoice &&
      hasIgtfContext &&
      typeof order._igtfBaseState === "function"
    ) {
      const requested = Number(amount) || 0;
      const { sign, remainingBase, unpaidIgtf } = order._igtfBaseState(this);
      const dueBase = order._igtfRoundLocal(sign * (remainingBase + unpaidIgtf));
      const dueForeign = order._igtfToForeign(dueBase);
      const requestedN = sign * requested;
      const dueN = sign * dueForeign;
      const overpayForeign = round_pr(requestedN - dueN, order.pos.foreign_currency.rounding);
      if (dueN > 0 && requestedN > 0 && overpayForeign >= 0) {
        this.foreign_amount = round_pr(requested, order.pos.foreign_currency.rounding);
        if (overpayForeign > 0) {
          return super.set_foreign_amount(...arguments);
        }
        this.amount = dueBase;
        return;
      }
    }
    return super.set_foreign_amount(...arguments);
  },
  init_from_JSON(json) {
    super.init_from_JSON(...arguments);
    this.include_igtf = json.include_igtf || false;
    this.igtf_amount = json.igtf_amount || 0;
    this.foreign_igtf_amount = json.foreign_igtf_amount || 0;
  },
  export_as_JSON() {
    let res = super.export_as_JSON();
    res["include_igtf"] = this.include_igtf;
    res["igtf_amount"] = this.igtf_amount;
    res["foreign_igtf_amount"] = this.foreign_igtf_amount;
    return res;
  },
});
