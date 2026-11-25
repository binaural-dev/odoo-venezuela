import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";
import { EQ, GT, LT } from "@point_of_sale/app/utils/numbers";

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
  _igtfGenerates(order) {
    // Whether the base this line covers generates IGTF: never on a refund that
    // gives back the IGTF of its sale (order._igtfRefundShare).
    return (
      this.appliesIgtf &&
      !(typeof order?._igtfRefundShare === "function" && order._igtfRefundShare())
    );
  },
  _igtfShownDue(sign, localDue) {
    // Magnitude, in the payment currency, of a local due as the cashier sees
    // it on screen (rounded to the payment currency).
    return this.currency.round(sign * this._localToPaymentCurrency(sign * localDue));
  },
  _igtfPanelTotal(order, sign, remainingBase, unpaidIgtf) {
    // "TOTAL a Pagar con IGTF" of the payment panel, in the payment currency,
    // when it is what this line still has to cover: the line applies IGTF, it
    // is in the currency the panel shows and nothing else has been paid yet.
    // 0 otherwise.
    if (
      !this._igtfGenerates(order) ||
      !this.usesAlternateEngine ||
      unpaidIgtf ||
      typeof order.get_foreign_total_with_igtf !== "function"
    ) {
      return 0;
    }
    const totalN = order._igtfRoundLocal(sign * order.get_total_without_igtf());
    if (order._igtfRoundLocal(remainingBase) !== totalN) {
      return 0;
    }
    return this.currency.round(sign * order.get_foreign_total_with_igtf());
  },
  _igtfCompare(a, b) {
    if (typeof this.currency.comp === "function") {
      return this.currency.comp(a, b);
    }
    const diff = this.currency.round(a - b);
    return diff > 0 ? GT : diff < 0 ? LT : EQ;
  },
  set_foreign_amount(amount) {
    // The "covers what is due" clamp of l10n_ve_pos does not know the IGTF
    // surcharge. With IGTF context (the payment applies IGTF, or the order
    // carries IGTF debt with any method) the due is the CURRENT remaining:
    // invoice base still to cover plus the IGTF debt. Three outcomes, all in
    // the payment currency as shown on screen:
    // - The typed amount is the due plus the IGTF this same line generates
    //   (the "TOTAL a Pagar con IGTF" of the panel): the line is worth exactly
    //   that in local currency. The panel adds the foreign total and the
    //   foreign IGTF rounded apart, so it can show one step more or less than
    //   the rounded sum: typing the panel figure also settles the order
    //   exactly (task 87707).
    // - The typed amount is the due shown: exactly the local due, and the IGTF
    //   it generates becomes the new remaining (two-line design).
    // - More than that: the whole tender is converted at the rate of its
    //   currency, never less than the due (task 87709).
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
      const dueN = order._igtfRoundLocal(remainingBase + unpaidIgtf);
      const fullN = this._igtfGenerates(order)
        ? order._igtfRoundLocal(dueN + order.compute_igtf_amount(remainingBase))
        : dueN;
      const typed = this.currency.round(requested);
      const requestedN = this.currency.round(sign * requested);
      const dueShownN = this._igtfShownDue(sign, dueN);
      const fullShownN = this._igtfShownDue(sign, fullN);
      const panelShownN = this._igtfPanelTotal(order, sign, remainingBase, unpaidIgtf);
      if (
        dueShownN > 0 &&
        requestedN > 0 &&
        this._igtfCompare(requestedN, dueShownN) !== LT
      ) {
        let amountN;
        if (
          this._igtfCompare(requestedN, fullShownN) === EQ ||
          (panelShownN && this._igtfCompare(requestedN, panelShownN) === EQ)
        ) {
          amountN = fullN;
        } else if (this._igtfCompare(requestedN, dueShownN) === EQ) {
          amountN = dueN;
        } else {
          const tenderN = sign * this._paymentCurrencyToLocal(sign * requestedN);
          amountN = tenderN > dueN ? tenderN : dueN;
        }
        this.amount = order._igtfRoundLocal(sign * amountN);
        this._stampForeignAmount(typed);
        return;
      }
    }
    return super.set_foreign_amount(...arguments);
  },
});
