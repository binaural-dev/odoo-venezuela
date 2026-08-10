/** @odoo-module */

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import {
  floatIsZero,
  roundPrecision as round_pr,
} from "@web/core/utils/numbers";

patch(Order.prototype, {
  setup(_defaultObj, options) {
    super.setup(...arguments);
    this.igtf_amount = 0;
    this.foreign_igtf_amount = 0;
    this.bi_igtf = 0;
    this.foreign_bi_igtf = 0;
    this.update_igtf();
  },
  init_from_JSON(json) {
    super.init_from_JSON(...arguments);
    this.igtf_amount = json.igtf_amount;
    this.bi_igtf = json.bi_igtf;
    this.foreign_igtf_amount = json.foreign_igtf_amount;
    this.foreign_bi_igtf = json.foreign_bi_igtf;
  },
  export_as_JSON() {
    let json = super.export_as_JSON();
    json["igtf_amount"] = this.igtf_amount;
    json["bi_igtf"] = this.bi_igtf;
    json["foreign_igtf_amount"] = this.foreign_igtf_amount;
    json["foreign_bi_igtf"] = this.foreign_bi_igtf;
    return json;
  },

  // --- Helpers de moneda ---
  _isBsBase() {
    return this.pos.currency.name === "VEF" || this.pos.currency.name === "VES";
  },
  _getBsRate() {
    if (this._isBsBase()) return 1;
    return this.pos.config.foreign_rate || 1;
  },
  _baseToBs(amount) {
    return amount * this._getBsRate();
  },
  _bsToBase(amount) {
    return amount / this._getBsRate();
  },
  _igtfRoundLocal(amount) {
    return round_pr(amount, this.pos.currency.rounding);
  },
  _igtfToForeign(amount) {
    return round_pr(
      amount * (this._isBsBase() ? this.pos.foreign_currency.rate : this._getBsRate()),
      this.pos.foreign_currency.rounding,
    );
  },
  _paidAmount() {
    let paid = 0;
    for (const line of this.get_paymentlines()) {
      if (!(line.amount < 0)) {
        paid += line.amount || 0;
      }
    }
    return paid;
  },

  // --- Algoritmo central IGTF ---
  _igtfBaseState(excludeLine = null) {
    const total = this.get_total_without_igtf();
    const sign = total < 0 ? -1 : 1;
    let remainingBase = this._igtfRoundLocal(sign * total);
    let unpaidIgtf = 0;
    const lines = [];
    for (const payment of this.get_paymentlines()) {
      if (excludeLine && payment === excludeLine) continue;
      const amt = this._igtfRoundLocal(sign * (payment.amount || 0));
      const isIgtf = Boolean(payment.payment_method?.apply_igtf);
      const isChange = amt < 0;
      if (isChange || floatIsZero(amt, this.pos.currency.decimal_places)) {
        lines.push({ payment, base: 0, newIgtf: 0, isChange, isIgtf });
        continue;
      }
      const base = amt < remainingBase ? amt : remainingBase;
      remainingBase = this._igtfRoundLocal(remainingBase - base);
      let newIgtf = 0;
      if (isIgtf) {
        newIgtf = this.compute_igtf_amount(base);
        unpaidIgtf = this._igtfRoundLocal(unpaidIgtf + newIgtf);
      }
      const excess = this._igtfRoundLocal(amt - base);
      if (excess > 0) {
        unpaidIgtf = excess < unpaidIgtf
          ? this._igtfRoundLocal(unpaidIgtf - excess)
          : 0;
      }
      lines.push({ payment, base, newIgtf, isChange, isIgtf });
    }
    return { sign, remainingBase, unpaidIgtf, lines };
  },
  update_igtf() {
    const paymentlines = this.get_paymentlines();

    this.igtf_amount = 0;
    this.foreign_igtf_amount = 0;
    this.bi_igtf = 0;
    this.foreign_bi_igtf = 0;

    paymentlines.forEach((payment) => {
      payment.set_include_igtf(false);
      payment.set_igtf_amount(0);
      payment.set_foreign_igtf_amount(0);
    });

    if (!this.to_invoice) {
      return this.igtf_amount;
    }

    const { sign, lines } = this._igtfBaseState();
    let totalIgtf = 0;
    let totalBase = 0;

    for (const { payment, base, newIgtf, isChange, isIgtf } of lines) {
      if (!isIgtf || isChange) continue;
      payment.set_include_igtf(true);
      payment.set_igtf_amount(sign * newIgtf);
      payment.set_foreign_igtf_amount(this._igtfToForeign(sign * newIgtf));
      totalIgtf += newIgtf;
      totalBase += base;
    }

    this.igtf_amount = this._igtfRoundLocal(sign * totalIgtf);
    this.foreign_igtf_amount = this._igtfToForeign(this.igtf_amount);
    this.bi_igtf = this._igtfRoundLocal(sign * totalBase);
    this.foreign_bi_igtf = this._igtfToForeign(this.bi_igtf);
    return this.igtf_amount;
  },
  compute_igtf_amount(baseAmount) {
    const bsAmount = this._baseToBs(baseAmount);
    const igtfInBs = this._igtfRoundLocal(bsAmount * (this.pos.config.igtf_percentage / 100));
    return this._bsToBase(igtfInBs);
  },

  get_bi_igtf() {
    return this.bi_igtf;
  },
  get_igtf_amount() {
    return this.igtf_amount;
  },
  get_foreign_igtf_amount() {
    return this.foreign_igtf_amount;
  },
  get_total_without_igtf() {
    return super.get_total_with_tax(...arguments);
  },
  get_foreign_total_without_igtf() {
    return super.get_foreign_total_with_tax(...arguments);
  },
  get_total_with_tax() {
    const res = super.get_total_with_tax(...arguments);
    return this._igtfRoundLocal(res + (this.igtf_amount || 0));
  },
  get_foreign_total_with_tax() {
    return this._igtfToForeign(this.get_total_with_tax());
  },

  // get_due incluye recargo IGTF para que la precarga de pagos sea correcta
  get_due() {
    const igtf = this._igtfRoundLocal(this.igtf_amount || 0);
    if (igtf === 0 || !this.to_invoice) {
      return super.get_due();
    }
    const total = this.get_total_without_igtf();
    const paid = this._paidAmount();
    const sign = total < 0 ? -1 : 1;
    const remaining = this._igtfRoundLocal(total + igtf - paid);
    if (sign * remaining <= 0) {
      return 0;
    }
    return remaining;
  },

  add_paymentline(payment_method) {
    const res = super.add_paymentline(...arguments);
    this.update_igtf();
    return res;
  },
});
