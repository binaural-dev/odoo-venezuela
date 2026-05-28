/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";
import {
  roundPrecision as round_pr,
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
    const rounding = this.pos?.currency?.rounding || 0.01;
    const foreignRounding = this.get_foreign_rounding?.() || this.get_foreign_currency?.()?.rounding || 0.01;
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

    const percentage =
      typeof payment_method?.igtf_percentage === "number"
        ? payment_method.igtf_percentage
        : this._get_order_igtf_percentage();

    return {
      orderAmount: round_pr(orderDue, rounding),
      foreignAmount: round_pr(foreignDue, foreignRounding),
    };
  },

  // --- MÉTODOS AUXILIARES PARA IGTF ---

  _is_change_payment(payment, is_return) {
    return is_return ? (payment.amount > 0) : (payment.amount < 0);
  },

  _get_payment_foreign_amount(payment) {
    if (!payment) {
      return 0;
    }
    if (typeof payment.get_foreign_amount === "function") {
      return payment.get_foreign_amount() || 0;
    }
    if (typeof payment.getForeignAmount === "function") {
      return payment.getForeignAmount() || 0;
    }
    return payment.foreign_amount || 0;
  },

  _normalize_remaining_amount(amount, orderTotal, is_return) {
    if (is_return) {
      return Math.max(orderTotal, Math.min(amount, 0));
    }
    return Math.min(orderTotal, Math.max(amount, 0));
  },

  _compute_line_igtf(amount, foreing_amount, percentage, is_return) {

    const rounding = this.pos?.currency?.rounding || 0.01;
    const foreignRounding = this.get_foreign_currency?.()?.rounding || 0.01;
    // Cuando la línea ya incluye IGTF, primero despejamos la base imponible.
    const gross_amount = Number(amount || 0);
    const gross_foreign_amount = Number(foreing_amount || 0);
    let amount_to_pay =  gross_amount;
    let foreign_amount_to_pay = gross_foreign_amount;

    // En ventas normales, una base positiva no debe producir un monto alterno negativo.
    if (!is_return && amount_to_pay >= 0 && foreign_amount_to_pay < 0) {
      foreign_amount_to_pay = 0;
    }

    if (is_return && amount_to_pay <= 0 && foreign_amount_to_pay > 0) {
      foreign_amount_to_pay = 0;
    }

    // Calcular el impuesto exacto redondeado
    const igtf_amount = round_pr(amount_to_pay * (percentage / 100), rounding);
    const foreign_igtf_amount = round_pr(
      foreign_amount_to_pay * (percentage / 100),
      foreignRounding,
    );

    return {
      base: round_pr(amount_to_pay, rounding),
      foreign_base: round_pr(foreign_amount_to_pay, foreignRounding),
      tax: igtf_amount,
      foreign_tax: foreign_igtf_amount
    };
  },

  // --- FIN MÉTODOS AUXILIARES ---

  update_igtf() {
    const paymentlines = this._get_order_payment_lines();
    const is_return = this.get_total_without_igtf() < 0;
    const rounding = this.pos?.currency?.rounding || 0.01;
    const foreignRounding = this.get_foreign_currency?.()?.rounding || 0.01;

    // 1. Reiniciar contadores globales de la orden
    this.igtf_amount = 0;
    this.foreign_igtf_amount = 0;
    this.bi_igtf = 0;
    this.foreign_bi_igtf = 0;

    // FIX: usar _is_invoice_order() — Odoo 19 no expone this.to_invoice directamente
    if (!this._is_invoice_order()) {
      paymentlines.forEach((payment) => {
        payment.set_include_igtf(false);
        payment.set_igtf_amount(0);
        payment.set_foreign_igtf_amount(0);
      });
      return 0;
    }

    const has_igtf_line = paymentlines.some((payment) => {
      const paymentMethod = this._get_payment_method_data(payment);
      return paymentMethod?.apply_igtf && !this._is_change_payment(payment, is_return);
    });

    if (!has_igtf_line) {
      paymentlines.forEach((payment) => {
        payment.set_include_igtf(false);
        payment.set_igtf_amount(0);
        payment.set_foreign_igtf_amount(0);
      });
      return 0;
    }

    let remaining_base = round_pr(this.get_total_without_igtf(), rounding);
    let remaining_foreign_base = round_pr(this.get_foreign_total_without_igtf(), foreignRounding);
    let has_processed_igtf_line = false;

    let total_bi_igtf = 0;
    let total_foreign_bi_igtf = 0;
    let total_igtf_amount = 0;
    let total_foreign_igtf_amount = 0;

    paymentlines.forEach((payment) => {
      const paymentMethod = this._get_payment_method_data(payment);
      if (this._is_change_payment(payment, is_return)) {
        payment.set_include_igtf(false);
        payment.set_igtf_amount(0);
        payment.set_foreign_igtf_amount(0);
        return;
      }

      const lineAmount = round_pr(payment.amount || 0, rounding);
      const lineForeignAmount = round_pr(this._get_payment_foreign_amount(payment), foreignRounding);

      if (!paymentMethod?.apply_igtf) {
        payment.set_include_igtf(false);
        payment.set_igtf_amount(0);
        payment.set_foreign_igtf_amount(0);

        if (!has_processed_igtf_line) {
          remaining_base = round_pr(remaining_base - lineAmount, rounding);
          remaining_foreign_base = round_pr(remaining_foreign_base - lineForeignAmount, foreignRounding);
        }
        return;
      }

      has_processed_igtf_line = true;

      payment.set_include_igtf(true);

      const percentage =
        typeof paymentMethod.igtf_percentage === "number"
          ? paymentMethod.igtf_percentage
          : this._get_order_igtf_percentage();

      const has_foreign_balance_pending = is_return
        ? remaining_foreign_base < (-foreignRounding / 2)
        : remaining_foreign_base > (foreignRounding / 2);

      const taxable_base = is_return
        ? Math.max(lineAmount, remaining_base)
        : Math.min(lineAmount, remaining_base);
      const taxable_foreign_base = has_foreign_balance_pending
        ? (
            is_return
              ? Math.max(lineForeignAmount, remaining_foreign_base)
              : Math.min(lineForeignAmount, remaining_foreign_base)
          )
        : 0;

      const computed = this._compute_line_igtf(
        taxable_base,
        taxable_foreign_base,
        percentage,
        is_return,
      );

      payment.set_igtf_amount(computed.tax);
      payment.set_foreign_igtf_amount(computed.foreign_tax);

      total_bi_igtf = round_pr(total_bi_igtf + (computed.base || 0), rounding);
      total_foreign_bi_igtf = round_pr(
        total_foreign_bi_igtf + (computed.foreign_base || 0),
        foreignRounding,
      );

      total_igtf_amount = round_pr(total_igtf_amount + (computed.tax || 0), rounding);
      total_foreign_igtf_amount = round_pr(
        total_foreign_igtf_amount + (computed.foreign_tax || 0),
        foreignRounding,
      );

      remaining_base = round_pr(remaining_base - (computed.base || 0), rounding);
      remaining_foreign_base = round_pr(
        remaining_foreign_base - (computed.foreign_base || 0),
        foreignRounding,
      );
    });

    // 5. Guardar totales consolidados en la orden
    this.bi_igtf = round_pr(total_bi_igtf, rounding);
    this.foreign_bi_igtf = round_pr(total_foreign_bi_igtf, foreignRounding);
    this.igtf_amount = round_pr(total_igtf_amount, rounding);
    this.foreign_igtf_amount = round_pr(total_foreign_igtf_amount, foreignRounding);

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
    const rounding = this.pos?.currency?.rounding || 0.01;
    return round_pr(amount * igtfPercentage / 100, rounding);
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
    const rounding = 0.01
    const res = this.get_total_with_tax(...arguments);
    return round_pr(res, rounding);
  },

  get_foreign_total_without_igtf() {
    const subtotal = this.get_foreign_total_without_tax?.(...arguments) || 0;
    const taxes = this.get_foreign_total_tax_per_line?.(...arguments) || 0;
    return subtotal + taxes;
  },

  set_total_from_backend(data) {
      if (data && typeof data === "object") {
          if ("amount_total" in data) {
              this.total_with_tax = data.amount_total;
          }
      }
      this.update_igtf();
      return true;
  },

  get totalDue() {
    const res = this.get_total_with_tax(...arguments);
    const rounding = 0.001
    const paymentlines = this._get_order_payment_lines();
    if (paymentlines.length === 0) {
      return round_pr(res, rounding);
    }
    const has_igtf_payment = paymentlines.some((payment) => {
      const paymentMethod = this._get_payment_method_data(payment);
      return paymentMethod?.apply_igtf;
    });
    if (!has_igtf_payment) {
      return round_pr(res, rounding);
    }
    return super.totalDue + this.get_igtf_amount()
  },

  get priceIncl() {
    const base = super.priceIncl;
    const rounding = 0.01
    const paymentlines = this._get_order_payment_lines();
    if (paymentlines.length === 0) {
      return round_pr(base, rounding);
    }

    const has_igtf_payment = paymentlines.some((payment) => {
      const paymentMethod = this._get_payment_method_data(payment);
      return paymentMethod?.apply_igtf;
    });
    if (!has_igtf_payment) {
      return round_pr(base, rounding);
    }

    return round_pr(base + this.get_igtf_amount(), rounding);
  },

  get_foreign_total_with_tax_custom() {
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
        return res + this.get_foreign_igtf_amount();
      }
    } else {
      return res;
    }
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
