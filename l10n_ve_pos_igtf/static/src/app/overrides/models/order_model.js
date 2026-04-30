/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";
import {
  formatFloat,
  roundDecimals as round_di,
  roundPrecision as round_pr,
  floatIsZero,
} from "@web/core/utils/numbers";

// New orders are now associated with the current table, if any.
patch(PosOrder.prototype, {
  setup() {
    super.setup(...arguments);
    this.igtf_amount = 0;
    this.foreign_igtf_amount = 0;
    this.bi_igtf = 0;
    this.foreign_bi_igtf = 0;
    console.log('POS:', this)
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


  _get_order_payment_lines() {
    if (typeof this.get_paymentlines === "function") {
      return this.get_paymentlines();
    }
    if (Array.isArray(this.paymentlines)) {
      return this.paymentlines;
    }
    if (Array.isArray(this.paymentlines?.models)) {
      return this.paymentlines.models;
    }
    if (Array.isArray(this.payment_ids)) {
      return this.payment_ids;
    }
    return [];
  },
  _get_payment_method_data(payment) {
    if (!payment) {
      return null;
    }

    if (payment.payment_method && typeof payment.payment_method === "object") {
      return payment.payment_method;
    }

    const paymentMethodIdValue = payment.payment_method_id;
    if (
      paymentMethodIdValue &&
      typeof paymentMethodIdValue === "object" &&
      !Array.isArray(paymentMethodIdValue)
    ) {
      return paymentMethodIdValue;
    }

    const paymentMethodIdRaw = Array.isArray(paymentMethodIdValue)
      ? paymentMethodIdValue[0]
      : paymentMethodIdValue;
    const paymentMethodId = Number(paymentMethodIdRaw);

    const posPaymentMethods = this.pos?.payment_methods;
    if (Array.isArray(posPaymentMethods)) {
      const byNumber = Number.isFinite(paymentMethodId)
        ? posPaymentMethods.find((method) => Number(method.id) === paymentMethodId)
        : null;
      if (byNumber) {
        return byNumber;
      }
      return (
        posPaymentMethods.find(
          (method) => String(method.id) === String(paymentMethodIdRaw),
        ) || null
      );
    }
    if (posPaymentMethods && typeof posPaymentMethods === "object") {
      if (Number.isFinite(paymentMethodId) && posPaymentMethods[paymentMethodId]) {
        return posPaymentMethods[paymentMethodId];
      }
      return posPaymentMethods[paymentMethodIdRaw] || null;
    }
    const paymentMethodModel = this.pos?.models?.["pos.payment.method"];
    if (Array.isArray(paymentMethodModel)) {
      return (
        paymentMethodModel.find(
          (method) => String(method.id) === String(paymentMethodIdRaw),
        ) || null
      );
    }
    if (paymentMethodModel?.get) {
      return (
        paymentMethodModel.get(paymentMethodId) ||
        paymentMethodModel.get(paymentMethodIdRaw) ||
        null
      );
    }
    return null;
  },
  update_igtf() {
    // var rounding = this.pos.config.currency.rounding;
    const paymentlines = this._get_order_payment_lines();
    // console.log('ENV IS', this)
    let igtf_payment_methods = paymentlines.filter((payment) => {
      const paymentMethod = this._get_payment_method_data(payment);
      return paymentMethod?.apply_igtf;
    });
    let last_igtf_amount = 0;
    let last_foreign_igtf_amount = 0;

    if (paymentlines.length > 0) {
      last_igtf_amount = this.igtf_amount;
      last_foreign_igtf_amount = this.foreign_igtf_amount;
    }
    let is_return = this.get_total_without_igtf() < 0;
    this.igtf_amount = 0;
    this.foreign_igtf_amount = 0;
    this.bi_igtf = 0;
    this.foreign_bi_igtf = 0;

    let bi_igtf = 0;
    let foreign_bi_igtf = 0;
    let repeat_same_method = [];
    let bi_payments = [];

    let igtf_amount = 0;
    let foreign_igtf_amount = 0;

    paymentlines.forEach((payment) => {
      payment.set_include_igtf(false);
    });

    if (!this.to_invoice) {
      return;
    }

    paymentlines.forEach((payment) => {
      const paymentMethod = this._get_payment_method_data(payment);
      let is_change = false;
      if (!is_return) {
        is_change = payment.amount < 0;
      } else {
        is_change = payment.amount > 0;
      }

      if (
        paymentMethod?.apply_igtf &&
        last_igtf_amount == payment.amount
      ) {
        return;
      }

      if (
        !paymentMethod?.apply_igtf &&
        igtf_payment_methods.length <= 0
      ) {
        foreign_bi_igtf = this.get_foreign_total_without_igtf();
        igtf_amount = 0;
        foreign_igtf_amount = 0;

        let payment_without_change = paymentlines.filter((payment) => {
          if (!bi_payments.includes(payment.cid)) {
            return false;
          }

          let is_change = false;
          if (!is_return) {
            is_change = payment.amount < 0;
          } else {
            is_change = payment.amount > 0;
          }

          if (is_change) {
            return false;
          }

          return true;
        });

        if (payment_without_change.length > 0) {
          payment_without_change.forEach((payment) => {
            if (!payment.include_igtf) {
              payment.set_igtf_amount(
                igtf_amount / payment_without_change.length,
              );
              payment.set_foreign_igtf_amount(
                foreign_igtf_amount / payment_without_change.length,
              );
              return;
            }
            // payment.set_igtf_amount(igtf_amount / payment_without_change.length)
            // payment.set_foreign_igtf_amount(foreign_igtf_amount / payment_without_change.length)
          });
        }
        return;
      }

      bi_igtf += round_pr(payment.amount, 6);
      foreign_bi_igtf += round_pr(payment.get_foreign_amount(), 6);
      if (paymentMethod?.id) {
        repeat_same_method.push(paymentMethod.id);
      }
      bi_payments.push(payment.cid);

      if (paymentMethod?.apply_igtf) {
        payment.set_include_igtf(true);
      }
      let amount_to_pay = payment.amount;
      let foreign_amount_to_pay = payment.get_foreign_amount();

      if (
        (payment.amount > this.get_total_with_tax() && !is_return) ||
        (payment.amount < this.get_total_with_tax() && is_return)
      ) {
        amount_to_pay = this.get_total_with_tax();
        foreign_amount_to_pay = this.get_foreign_total_with_tax();
      }

      if (!is_change) {
        payment.set_igtf_amount(
          this.compute_igtf_amount(
            amount_to_pay,
            paymentMethod?.igtf_percentage,
          ),
        );
        payment.set_foreign_igtf_amount(
          this.compute_igtf_amount(
            foreign_amount_to_pay,
            paymentMethod?.igtf_percentage,
          ),
        );

        igtf_amount += payment.igtf_amount;
        foreign_igtf_amount += payment.foreign_igtf_amount;
      } else {
        payment.set_include_igtf(false);
      }
    });

    if (
      bi_igtf !== 0 &&
      bi_igtf >= this.get_total_without_igtf() &&
      !is_return
    ) {
      bi_igtf = this.get_total_without_igtf();
      foreign_bi_igtf = this.get_foreign_total_without_igtf();
      igtf_amount = this.compute_igtf_amount(
        bi_igtf,
        this._get_order_igtf_percentage(),
      );
      foreign_igtf_amount = this.compute_igtf_amount(
        foreign_bi_igtf,
        this._get_order_igtf_percentage(),
      );

      let payment_without_change = paymentlines.filter((payment) => {
        if (!bi_payments.includes(payment.cid)) {
          return false;
        }

        let is_change = false;
        if (!is_return) {
          is_change = payment.amount < 0;
        } else {
          is_change = payment.amount > 0;
        }

        if (is_change) {
          return false;
        }

        return true;
      });

      if (payment_without_change.length > 0) {
        payment_without_change.forEach((payment) => {
          if (!payment.include_igtf) {
            return;
          }
          // payment.set_igtf_amount(igtf_amount / payment_without_change.length)
          // payment.set_foreign_igtf_amount(foreign_igtf_amount / payment_without_change.length)
        });
      }
    }

    if (igtf_payment_methods.length > 0) {
      let amount_sum = 0;
      let foreign_amount_sum = 0;
      let igtf_amount_sum = 0;
      let foreign_igtf_amount_sum = 0;

      for (let payments of igtf_payment_methods) {
        amount_sum += payments.amount;
        foreign_amount_sum += payments.foreign_amount;
        igtf_amount_sum += payments.igtf_amount;
        foreign_igtf_amount_sum += payments.foreign_igtf_amount;
      }
      this.bi_igtf = amount_sum;
      this.foreign_bi_igtf = foreign_amount_sum;
      this.igtf_amount = igtf_amount_sum;
      this.foreign_igtf_amount = foreign_igtf_amount_sum;
    }
    return this.igtf_amount;
  },
  _get_order_igtf_percentage() {
    const paymentlines = this._get_order_payment_lines();
    const paymentWithIgtf = paymentlines.find((payment) => {
      const paymentMethod = this._get_payment_method_data(payment);
      return paymentMethod?.apply_igtf;
    });
    const paymentMethod = this._get_payment_method_data(paymentWithIgtf);
    const fromMethod = paymentMethod?.igtf_percentage;
    if (typeof fromMethod === "number") {
      return fromMethod;
    }
    return this.pos.config.igtf_percentage || 0;
  },

  compute_igtf_amount(amount, percentage = false) {
    var rounding = this.pos.config.currency.rounding;
    const igtfPercentage =
      typeof percentage === "number"
        ? percentage
        : this._get_order_igtf_percentage();
    return round_pr(amount * (igtfPercentage / 100), rounding);
  },

  get_bi_igtf() {
    return this.bi_igtf;
  },

  get_total_with_tax() {
    if (typeof this.total_with_tax === "number") {
      return this.total_with_tax;
    }
    const total_without_tax =
      (typeof this.get_total_without_tax === "function" &&
        this.get_total_without_tax(...arguments)) || 0;
    const total_tax =
      (typeof this.get_total_tax === "function" &&
        this.get_total_tax(...arguments)) || 0;
    return total_without_tax + total_tax;
  },

  get_total_without_igtf() {
    const res = this.get_total_with_tax(...arguments);
    return res;
  },

  get_foreign_total_without_igtf() {
    const subtotal = this.get_foreign_total_without_tax?.(...arguments) || 0;
    const taxes = this.get_foreign_total_tax_per_line?.(...arguments) || 0;
    return subtotal + taxes;
  },

  totalDue() {
    const res = this.get_total_with_tax(...arguments);
    const paymentlines = this._get_order_payment_lines();
    if (paymentlines.length === 0) {
      return res;
    }

    const has_igtf_payment = paymentlines.some((payment) => {
      const paymentMethod = this._get_payment_method_data(payment);
      return paymentMethod?.apply_igtf;
    });
    return has_igtf_payment ? res + this.igtf_amount : res;
  },

  foreignTotalDue() {
    const res = this.get_foreign_total_without_igtf(...arguments);
    const paymentlines = this._get_order_payment_lines();
    if (paymentlines.length === 0) {
      return res;
    }

    const has_igtf_payment = paymentlines.some((payment) => {
      const paymentMethod = this._get_payment_method_data(payment);
      return paymentMethod?.apply_igtf;
    });
    return has_igtf_payment ? res + this.foreign_igtf_amount : res;
  },

  get_foreign_total_with_tax() {
    const res = this.get_foreign_total_without_igtf(...arguments);
    const paymentlines = this._get_order_payment_lines();
    if (paymentlines.length > 0) {
      let igtf_payment_methods = paymentlines.filter((payment) => {
        const paymentMethod = this._get_payment_method_data(payment);
        return paymentMethod?.apply_igtf;
      });
      if (igtf_payment_methods.length === 0) {
        return res;
      } else {
        for (let payment of paymentlines) {
          const paymentMethod = this._get_payment_method_data(payment);
          if (paymentMethod?.apply_igtf) {
            return res + this.foreign_igtf_amount;
          }
        }
      }
    } else {
      return res;
    }
  },
  
  // get_foreign_total_with_tax() {
  //   const res = super.get_foreign_total_with_tax(...arguments);
  //   // let paymentlines = this.get_paymentlines();
  //   if (paymentlines.length > 0) {
  //     let igtf_payment_methods = paymentlines.filter(
  //       (payment) => payment.payment_method.apply_igtf,
  //     );
  //     if (igtf_payment_methods.length === 0) {
  //       return res;
  //     } else {
  //       for (let payment of paymentlines) {
  //         if (payment.payment_method.apply_igtf) {
  //           return res + this.foreign_igtf_amount;
  //         }
  //       }
  //     }
  //   } else {
  //     return res;
  //   }
  // },
  // get_max_total_with_igtf() {
  //   const result =
  //     this.compute_igtf_amount(super.get_foreign_total_with_tax()) +
  //     this.props.order.get_foreign_rounding_applied();
  //   return result;
  // },

  get_igtf_amount() {
    return this.igtf_amount;
  },

  get_foreign_igtf_amount() {
    return this.foreign_igtf_amount;
  },
  add_paymentline(payment_method) {
    let is_change = false;
    let is_return = this.get_total_without_igtf() < 0;
    if (!is_return) {
      is_change = this.get_due() < 0;
    } else {
      is_change = this.get_due() > 0;
    }

    if (
      !payment_method.apply_igtf ||
      this.get_due() <= this.get_igtf_amount() ||
      is_change
    ) {
      let res = super.add_paymentline(...arguments);
      // this.update_igtf();
      return res;
    }
    let res_igtf = this.add_paymentline_without_igtf(...arguments);
    // this.update_igtf();
    return res_igtf;
  },

  add_paymentline_without_igtf(payment_method) {
    this.assert_editable();
    if (this.electronic_payment_in_progress()) {
      return false;
    } else {
      var newPaymentline = new PosPayment(
        { env: this.env },
        { order: this, payment_method: payment_method, pos: this.pos },
      );
      this.paymentlines.add(newPaymentline);
      this.select_paymentline(newPaymentline);
      if (this.pos.config.cash_rounding) {
        this.selected_paymentline.set_amount(0);
      }

      newPaymentline.set_foreign_amount(
        this.get_foreign_due() - this.get_foreign_igtf_amount(),
        true,
      );
      newPaymentline.set_amount(this.get_due() - this.get_igtf_amount(), true);

      if (payment_method.payment_terminal) {
        newPaymentline.set_payment_status("pending");
      }
      return newPaymentline;
    }
  },
});
