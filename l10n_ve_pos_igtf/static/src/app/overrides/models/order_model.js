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

patch(PosOrder.prototype, {
  setup() {
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

  _is_invoice_order() {
    if (typeof this.is_to_receipt === "function") {
      return !this.is_to_receipt();
    }
    if (typeof this.to_invoice === "boolean") {
      return this.to_invoice;
    }
    return true;
  },

  _has_any_igtf_payment_line() {
    const paymentlines = this._get_order_payment_lines();
    return paymentlines.some((payment) => {
      const paymentMethod = this._get_payment_method_data(payment);
      return paymentMethod?.apply_igtf;
    });
  },

  _get_default_payment_amounts(payment_method) {
    const orderDue = this.get_due?.() || 0;
    const foreignDue = this.get_foreign_due?.() || 0;

    if (!this._is_invoice_order()) {
      return {
        orderAmount: orderDue,
        foreignAmount: foreignDue,
      };
    }

    if (!payment_method?.apply_igtf) {
      return {
        orderAmount: orderDue,
        foreignAmount: foreignDue,
      };
    }

    // If an IGTF line already exists, remaining due is already in IGTF context.
    if (this._has_any_igtf_payment_line()) {
      return {
        orderAmount: orderDue,
        foreignAmount: foreignDue,
      };
    }

    const percentage =
      typeof payment_method?.igtf_percentage === "number"
        ? payment_method.igtf_percentage
        : this._get_order_igtf_percentage();

    return {
      orderAmount: orderDue + this.compute_igtf_amount(orderDue, percentage),
      foreignAmount:
        foreignDue + this.compute_igtf_amount(foreignDue, percentage),
    };
  },

  update_igtf() {

    const paymentlines = this._get_order_payment_lines();
    
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

    if (!this._is_invoice_order()) {
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
            payment.set_igtf_amount(0)
            payment.set_foreign_igtf_amount(0)
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
          // Keep per-line IGTF based on each line amount, no proration by line count.
        });
      }
    }

    if (igtf_payment_methods.length > 0) {
      
      let amount_sum = 0;
      let foreign_amount_sum = 0;
      let igtf_amount_sum = 0;
      let foreign_igtf_amount_sum = 0;

      for (let payments of igtf_payment_methods) {
        const paymentMethod = this._get_payment_method_data(payments);
        const percentage =
          typeof paymentMethod?.igtf_percentage === "number"
            ? paymentMethod.igtf_percentage
            : this._get_order_igtf_percentage();
        const divisor = 1 + percentage / 100;

        const rawAmount = Number(payments.amount || 0);
        const rawForeignAmount = Number(
          payments.foreign_amount ?? payments.get_foreign_amount?.() ?? 0,
        );

        // If the payment line amount already includes IGTF, recover net taxable base.
        const baseAmount = percentage > 0 ? rawAmount / divisor : rawAmount;
        const foreignBaseAmount =
          percentage > 0 ? rawForeignAmount / divisor : rawForeignAmount;

        amount_sum += baseAmount;
        foreign_amount_sum += foreignBaseAmount;
        igtf_amount_sum += Number(payments.igtf_amount || 0);
        foreign_igtf_amount_sum += Number(payments.foreign_igtf_amount || 0);
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
    return this.config.igtf_percentage || 0;
  },

  compute_igtf_amount(amount, percentage = false) {
    const igtfPercentage =
      typeof percentage === "number"
        ? percentage
        : this._get_order_igtf_percentage();
    return amount * igtfPercentage / 100;
  },

  get_bi_igtf() {
    return this.bi_igtf;
  },

  get_total_with_tax() {

    if (typeof this.total_with_tax === "number") {
      return this.total_with_tax;
    }

    const total_without_tax = this.priceExcl || 0
    const total_tax = this.amountTaxes || 0

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

  get totalDue() {
    const res = this.get_total_with_tax(...arguments);
    const paymentlines = this._get_order_payment_lines();
    if (paymentlines.length === 0) {
      return res;
    }

    const has_igtf_payment = paymentlines.some((payment) => {
      const paymentMethod = this._get_payment_method_data(payment);
      return paymentMethod?.apply_igtf;
    });
    if (!has_igtf_payment) {
      return res;
    }
    return res + this.compute_igtf_amount(res, this._get_order_igtf_percentage());
  },

  get priceIncl() {
    const base = super.priceIncl;
    const paymentlines = this._get_order_payment_lines();
    if (paymentlines.length === 0) {
      return base;
    }

    const has_igtf_payment = paymentlines.some((payment) => {
      const paymentMethod = this._get_payment_method_data(payment);
      return paymentMethod?.apply_igtf;
    });
    if (!has_igtf_payment) {
      return base;
    }

    return base + this.compute_igtf_amount(base, this._get_order_igtf_percentage());
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
        return (
          res +
          this.compute_igtf_amount(res, this._get_order_igtf_percentage())
        );
      }
    } else {
      return res;
    }
  },


  getDefaultAmountDueToPayIn(paymentMethod) {
    const baseAmount = super.getDefaultAmountDueToPayIn(...arguments);
    if (!this._is_invoice_order()) {
      return baseAmount;
    }

    if (!paymentMethod?.apply_igtf) {
      return baseAmount;
    }

    // Avoid adding IGTF twice when the order already has an IGTF payment context.
    if (this._has_any_igtf_payment_line()) {
      return baseAmount;
    }

    const percentage =
      typeof paymentMethod?.igtf_percentage === "number"
        ? paymentMethod.igtf_percentage
        : this._get_order_igtf_percentage();

    return baseAmount + this.compute_igtf_amount(baseAmount, percentage);
  },

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
      this.update_igtf();
      return res;
    }
    let res_igtf = this.add_paymentline_without_igtf(...arguments);
    this.update_igtf();
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

      const defaultAmounts = this._get_default_payment_amounts(payment_method);

      newPaymentline.set_foreign_amount(
        defaultAmounts.foreignAmount,
        true,
      );
      newPaymentline.set_amount(defaultAmounts.orderAmount, true);

      if (payment_method.payment_terminal) {
        newPaymentline.set_payment_status("pending");
      }
      return newPaymentline;
    }
  },
});
