import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";

patch(PosPayment.prototype, {
  setup(vals) {
    super.setup(...arguments);
    this.igtf_amount = vals.igtf_amount || 0;
    this.foreign_igtf_amount = vals.foreign_igtf_amount || 0;
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
  get appliesIgtf() {
    return Boolean(this.currencySettings?.apply_igtf);
  },
  set_foreign_amount(amount) {
    // The "covers what is due" clamp of l10n_ve_pos does not know the IGTF
    // surcharge: it takes the due from totalDue (without the IGTF debt) and
    // converting the foreign excess back to local brings rounding noise (351
    // vs 348 Bs when paying the IGTF debt). With IGTF context (the payment
    // applies IGTF, or the order carries IGTF debt with any method) the due is
    // the CURRENT remaining: invoice base still to cover plus the IGTF debt,
    // without the IGTF this line will generate (it is born later, in
    // update_igtf). When the typed amount covers it, the local amount is set
    // to exactly that, with no conversion round trip.
    const order = this.pos_order_id;
    const hasIgtfContext =
      this.appliesIgtf ||
      (typeof order?._igtfRoundLocal === "function" &&
        order._igtfRoundLocal(order.igtf_amount || 0) !== 0);
    if (
      order?.to_invoice &&
      hasIgtfContext &&
      typeof order._igtfBaseState === "function"
    ) {
      const requested = Number(amount) || 0;
      const { sign, remainingBase, unpaidIgtf } = order._igtfBaseState(this);
      const dueLocal = order._igtfRoundLocal(sign * (remainingBase + unpaidIgtf));
      const typed = this.currency.round(requested);
      const dueForeign = this._localToPaymentCurrency(dueLocal);
      const requestedN = sign * requested;
      const dueN = sign * dueForeign;
      const overpayForeign = this.currency.round(requestedN - dueN);
      if (dueN > 0 && requestedN > 0 && overpayForeign >= 0) {
        const overpayLocal =
          overpayForeign > 0 ? this._paymentCurrencyToLocal(overpayForeign) : 0;
        this.amount = order._igtfRoundLocal(dueLocal + sign * overpayLocal);
        this._stampForeignAmount(typed);
        return;
      }
    }
    return super.set_foreign_amount(...arguments);
  },
});
