/** @odoo-module */
import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { patch } from "@web/core/utils/patch";

patch(PaymentScreenStatus.prototype, {
  _toNumber(value, fallback = 0) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
  },

  _callOrderNumber(methodName, fallback = 0, ...args) {
    const order = this.props?.order;
    if (!order || typeof order[methodName] !== "function") {
      return fallback;
    }
    return this._toNumber(order[methodName](...args), fallback);
  },

  _getConversionRate() {
    const order = this.props?.order;
    const candidates = [
      typeof order?.get_conversion_rate === "function" ? order.get_conversion_rate() : undefined,
      order?.init_conversion_rate,
      order?.config?.foreign_inverse_rate,
      order?.pos?.config?.foreign_inverse_rate,
      order?.config?.foreign_rate,
      order?.pos?.config?.foreign_rate,
    ];

    for (const candidate of candidates) {
      const numeric = Number(candidate);
      if (Number.isFinite(numeric) && numeric > 0) {
        return numeric;
      }
    }
    return 0;
  },

  _convertLocalToForeign(amount) {
    const localAmount = this._toNumber(amount, 0);
    const rate = this._getConversionRate();
    if (!rate) {
      return localAmount;
    }
    return rate >= 1 ? localAmount / rate : localAmount * rate;
  },

  _getForeignRoundingApplied() {
    const foreignRounding = this._callOrderNumber("get_foreign_rounding_applied", NaN);
    if (Number.isFinite(foreignRounding)) {
      return foreignRounding;
    }
    const localRounding = this._callOrderNumber("get_rounding_applied", 0);
    return this._convertLocalToForeign(localRounding);
  },

  _hasIgtfPaymentMethod() {
    const paymentLines = this.props?.order?.get_paymentlines?.() || [];
    return paymentLines.some((payment) => payment?.payment_method?.apply_igtf);
  },

  _getForeignTotalDueAmount() {
    const order = this.props?.order;
    const foreignTotalWithTax = this._callOrderNumber("get_foreign_total_with_tax", NaN);
    const totalWithTax = this._callOrderNumber("get_total_with_tax", order?.totalDue ?? 0);

    const baseAmount = Number.isFinite(foreignTotalWithTax)
      ? foreignTotalWithTax
      : this._convertLocalToForeign(totalWithTax);

    let amount = baseAmount + this._getForeignRoundingApplied();
    if (this._hasIgtfPaymentMethod()) {
      amount += this._callOrderNumber("get_foreign_igtf_amount", 0);
    }
    return amount;
  },

  _getForeignRemainingAmount() {
    const order = this.props?.order;
    const foreignDue = this._callOrderNumber("get_foreign_due", NaN);
    if (Number.isFinite(foreignDue)) {
      return Math.max(0, foreignDue);
    }
    const localDue = this._toNumber(order?.remainingDue ?? this._callOrderNumber("get_due", 0), 0);
    return Math.max(0, this._convertLocalToForeign(localDue));
  },

  _getForeignChangeAmount() {
    const order = this.props?.order;
    const foreignChange = this._callOrderNumber("get_foreign_change", NaN);
    if (Number.isFinite(foreignChange)) {
      return foreignChange;
    }
    const localChange = this._toNumber(order?.change ?? this._callOrderNumber("get_change", 0), 0);
    return this._convertLocalToForeign(localChange);
  },

  get foreignTotalDueText() {
    return this.env.utils.formatForeignCurrency(this._getForeignTotalDueAmount());
  },

  get foreignRemainingText() {
    return this.env.utils.formatForeignCurrency(this._getForeignRemainingAmount());
  },

  get foreignChangeText() {
    return this.env.utils.formatForeignCurrency(this._getForeignChangeAmount());
  },

  get currentOrder() {
    return this.props.order;
  },
});
