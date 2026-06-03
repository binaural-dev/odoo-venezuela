/** @odoo-module */

import { PosOrder } from "@point_of_sale/app/models/pos_order";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";

import {
  formatFloat,
  roundDecimals as round_di,
  roundPrecision as round_pr,
  floatIsZero,
} from "@web/core/utils/numbers";


patch(PosOrder.prototype, {
  _get_pos_store() {
    return this.pos || this.env?.services?.pos || this.env?.pos || null;
  },

  setup() {
    super.setup(...arguments);
  },

  get_foreign_currency() {
    return this.config.foreign_currency_id;
  },

  get_display_rate() {
    const posStore = this._get_pos_store();
    return posStore?.config?.foreign_rate || this.config?.foreign_rate || 1;
  },

  get_foreign_inverse_rate() {
    const posStore = this._get_pos_store();
    return posStore?.config?.foreign_inverse_rate || this.config?.foreign_inverse_rate || 1;
  },

  assert_editable() { },

  get init_conversion_rate() {
    if (this.currency.name == "VEF") {
      const companyId = this.user;
      return this.config.foreign_rate;
    }
  },

  add_orderline(line) {
    let res = super.add_orderline(...arguments);
    this.reload_taxes();
    return res;
  },

  get_conversion_rate() {
    const orderlines = this.currentOrder?.get_orderlines() || [];
    if (orderlines.length != 0) {
      return orderlines[0].currency_rate_display();
    }
    return this.init_conversion_rate || this.config.foreign_rate || 1.0;
  },

  get_orderlines() {
    return this.lines;
  },

  toggle_receipt_invoice(to_receipt) {
    if (this.getHasRefundLines()) {
      return;
    }
    this.assert_editable();
    this.to_receipt = to_receipt;
    this.to_invoice = !to_receipt;
  },
  
  export_as_JSON() {
    let json = super.export_as_JSON();
    json["foreign_amount_total"] = this.get_foreign_total_with_taxes();
    json["foreign_currency_rate"] = this.get_conversion_rate?.() || this.get_display_rate?.() || 0;
    json["to_receipt"] = this.is_to_receipt();
    return json;
  },

  serializeForORM(opts = {}) {
    const data = super.serializeForORM(opts);
    data.foreign_amount_total = this.get_foreign_total_with_taxes();
    data.foreign_currency_rate = this.get_conversion_rate?.() || this.get_display_rate?.() || 0;
    return data;
  },

  is_to_receipt() {
    return this.to_receipt;
  },

  export_for_printing() {
    let res = super.export_for_printing(...arguments);
    let new_res = {
      ...res,
      foreign_amount_total: this.get_foreign_total_with_taxes(),
      foreign_total_without_tax: this.get_foreign_total_without_tax(),
      foreign_amount_tax: this.get_foreign_total_tax(),
      foreign_total_paid: this.get_foreign_total_paid(),
    };
    return new_res;
  },
  set_orderline_options(orderline, options) {
    super.set_orderline_options(...arguments);
    if (options.foreign_price !== undefined) {
      orderline.set_foreign_unit_price(options.foreign_price);
    }
  },

  calculate_foreign_base_amount(tax_ids_array, lines) {
    // Consider price_include taxes use case
    const has_taxes_included_in_price = tax_ids_array.filter(
      (tax_id) => this.pos.taxes_by_id[tax_id].price_include,
    ).length;

    const base_amount = lines.reduce(
      (sum, line) =>
        sum +
        line.get_foreign_price_without_tax() +
        (has_taxes_included_in_price
          ? line.get_foreign_total_taxes_included_in_price()
          : 0),
      0,
    );
    return base_amount;
  },

  /* ---- Payment Status --- */
  get_foreign_subtotal() {
    return round_pr(
      this.orderlines.reduce(function (sum, orderLine) {
        return sum + orderLine.get_display_foreign_price();
      }, 0),
      this.pos.foreign_currency.rounding,
    );
  },

  get_foreign_total_with_taxes() {
    const rounding = this.get_foreign_currency()?.rounding || 0.01;
    return round_pr((this.get_foreign_total_without_tax() || 0) + (this.get_foreign_total_tax_per_line() || 0), rounding)
  },

  get foreign_total_with_taxes() {
    return this.get_foreign_total_with_taxes()
  },

  get_foreign_total_without_tax() {
    const lines = this.get_orderlines();
    const foreign_currency = this.get_foreign_currency();

    const total = lines.reduce((acumulador, line) => {
      const linePrices = line.get_all_foreign_prices ? line.get_all_foreign_prices() : { priceWithoutTax: 0 };
      return acumulador + (linePrices.priceWithoutTax || 0);
    }, 0);
    return total

  },

  get_foreign_total_discount() {
    const ignored_product_ids = this._get_ignored_product_ids_total_discount();
    return round_pr(
      this.orderlines.reduce((sum, orderLine) => {
        if (!ignored_product_ids.includes(orderLine.product.id)) {
          sum +=
            orderLine.getForeignUnitDisplayPriceBeforeDiscount() *
            (orderLine.get_discount() / 100) *
            orderLine.getQuantity();
          if (orderLine.display_discount_policy() === "without_discount") {
            sum +=
              (orderLine.get_taxed_lst_unit_foreign_price() -
                orderLine.getForeignUnitDisplayPriceBeforeDiscount()) *
              orderLine.getQuantity();
          }
        }
        return sum;
      }, 0),
      this.pos.foreign_currency.rounding,
    );
  },

  get_foreign_total_tax() {
    const orderlines = this.get_orderlines();
    const foreignCurrency = this.get_foreign_currency();
    const rounding = foreignCurrency?.rounding || 0.01;
    let totalTax = 0;

    if (this.company.tax_calculation_rounding_method === "round_globally") {

      const groupTaxes = orderlines.reduce((acc, line) => {

        const taxDetails = line.get_foreign_tax_details?.() || {};
        for (const [taxId, detail] of Object.entries(taxDetails)) {
          acc[taxId] = (acc[taxId] || 0) + (detail.amount || 0);
        }
        return acc;
      }, {});

      totalTax = Object.values(groupTaxes).reduce(
        (sum, amount) => sum + amount,
        0
      );
    } else {
      totalTax = orderlines.reduce((sum, line) => {
        const lineTax = line.get_all_foreign_prices ? line.get_all_foreign_prices().tax : (line.get_foreign_tax?.() || line.get_foreign_total_tax?.() || 0);
        return sum + lineTax;
      }, 0);
    }
    return totalTax;
  },

  get_foreign_total_tax_per_line() {
    const orderlines = this.get_orderlines();
    const foreignCurrency = this.get_foreign_currency();
    const rounding = foreignCurrency?.rounding || 0.01;

    const totalTax = orderlines.reduce((sum, line) => {
      const tax_amounts = line.get_all_foreign_prices ? line.get_all_foreign_prices() : { tax: 0 };
      return sum + (tax_amounts.tax || 0);
    }, 0);

    return totalTax;
  },

  get_foreign_tax_details() {
    var details = {};
    var fulldetails = [];

    this.orderlines.forEach(function (line) {
      var ldetails = line.get_foreign_tax_details();
      for (var id in ldetails) {
        if (Object.hasOwnProperty.call(ldetails, id)) {
          details[id] = {
            amount: (details[id]?.amount || 0) + ldetails[id].amount,
            base: (details[id]?.base || 0) + ldetails[id].base,
          };
        }
      }
    });

    for (var id in details) {
      if (Object.hasOwnProperty.call(details, id)) {
        fulldetails.push({
          amount: details[id].amount,
          base: details[id].base,
          tax: this.pos.taxes_by_id[id],
          name: this.pos.taxes_by_id[id].name,
        });
      }
    }

    return fulldetails;
  },

  get_foreign_total_for_taxes(tax_id) {
    var total = 0;

    if (!(tax_id instanceof Array)) {
      tax_id = [tax_id];
    }

    var tax_set = {};

    for (var i = 0; i < tax_id.length; i++) {
      tax_set[tax_id[i]] = true;
    }

    this.orderlines.forEach((line) => {
      var taxes_ids = this.tax_ids || line.getProduct().taxes_id;
      for (var i = 0; i < taxes_ids.length; i++) {
        if (tax_set[taxes_ids[i]]) {
          total += line.get_foreign_price_with_tax();
          return;
        }
      }
    });

    return total;
  },

  async pay() {
    let order = this.pos.get_order();
    let lines = order.get_orderlines();
    console.log('LINEAS DE ORDEN', lines)

    if (order.getHasRefundLines()) {
      return await super.pay();
    }
    await this.pos.update_products(order);

    if (this.pos.config.amount_to_zero) {
      let product_quantity_by_product = {};
      let products = [];
      for (let line of lines) {
        let prd = this.pos.db.getProduct_by_id(line.getProduct().id);

        if (prd.type != "product") {
          continue;
        }

        if (product_quantity_by_product[prd.id] == undefined) {
          product_quantity_by_product[prd.id] = 0;
        }
        product_quantity_by_product[prd.id] =
          product_quantity_by_product[prd.id] + line.quantity;
        if (
          product_quantity_by_product[prd.id] > prd.qty_available ||
          prd.qty_available <= 0
        ) {
          products.push(prd.display_name);
        }
      }

      if (products.length > 0)
        return this.env.services.popup.add(ErrorPopup, {
          title: _t("Validate Product in Warehouse"),
          body: _t(
            "The product %s You do not have enough stock in the warehouse",
            products,
          ),
        });
    }
    return await super.pay(...arguments);
  },

  get_foreign_rounding_applied() {
    if (this.config.cash_rounding) {
      const only_cash = this.config.only_round_cash_method;
      const paymentlines = this.get_paymentlines();
      const last_line = paymentlines
        ? paymentlines[paymentlines.length - 1]
        : false;
      const last_line_is_cash = last_line
        ? last_line.payment_method.is_cash_count == true
        : false;
      if (!only_cash || (only_cash && last_line_is_cash)) {
        var rounding_method = this.pos.cash_rounding[0].rounding_method;
        var remaining =
          this.get_foreign_total_with_taxes() - this.get_total_paid();
        var sign = this.get_foreign_total_with_taxes() > 0 ? 1.0 : -1.0;
        if (
          ((this.get_foreign_total_with_taxes() < 0 && remaining > 0) ||
            (this.get_foreign_total_with_taxes() > 0 && remaining < 0)) &&
          rounding_method !== "HALF-UP"
        ) {
          rounding_method = rounding_method === "UP" ? "DOWN" : "UP";
        }

        remaining *= sign;
        var total = round_pr(remaining, this.pos.cash_rounding[0].rounding);
        var rounding_applied = total - remaining;

        // because floor and ceil doesn't include decimals in calculation, we reuse the value of the half-up and adapt it.
        if (
          floatIsZero(
            rounding_applied,
            this.pos.foreign_currency.decimal_places,
          )
        ) {
          // https://xkcd.com/217/
          return 0;
        } else if (
          Math.abs(this.get_foreign_total_with_taxes()) <
          this.pos.cash_rounding[0].rounding
        ) {
          return 0;
        } else if (
          rounding_method === "UP" &&
          rounding_applied < 0 &&
          remaining > 0
        ) {
          rounding_applied += this.pos.cash_rounding[0].rounding;
        } else if (
          rounding_method === "UP" &&
          rounding_applied > 0 &&
          remaining < 0
        ) {
          rounding_applied -= this.pos.cash_rounding[0].rounding;
        } else if (
          rounding_method === "DOWN" &&
          rounding_applied > 0 &&
          remaining > 0
        ) {
          rounding_applied -= this.pos.cash_rounding[0].rounding;
        } else if (
          rounding_method === "DOWN" &&
          rounding_applied < 0 &&
          remaining < 0
        ) {
          rounding_applied += this.pos.cash_rounding[0].rounding;
        } else if (
          rounding_method === "HALF-UP" &&
          rounding_applied === this.pos.cash_rounding[0].rounding / -2
        ) {
          rounding_applied += this.pos.cash_rounding[0].rounding;
        }
        return sign * rounding_applied;
      } else {
        return 0;
      }
    }
    return 0;
  },

  get_rounding_applied() {
    if (typeof super.get_rounding_applied === "function") {
      const value = super.get_rounding_applied(...arguments);
      return Number.isFinite(value) ? value : 0;
    }

    if (typeof this.getRoundingApplied === "function") {
      const value = this.getRoundingApplied(...arguments);
      return Number.isFinite(value) ? value : 0;
    }

    if (typeof this.appliedRounding === "number") {
      return Number.isFinite(this.appliedRounding) ? this.appliedRounding : 0;
    }

    return 0;
  },

  get_foreign_rounding() {
    return (
      this.pos?.foreign_currency?.rounding ||
      this.get_foreign_currency()?.rounding ||
      0.01
    );
  },

  get_order_payment_lines() {
    return this.get_paymentlines?.() || this.paymentlines || this.payment_ids || [];
  },

  get_payment_foreign_amount(paymentLine) {
    if (!paymentLine) {
      return 0;
    }

    const foreignAmount =
      (typeof paymentLine.get_foreign_amount === "function" && paymentLine.get_foreign_amount()) ??
      paymentLine.foreign_amount;

    return Number.isFinite(foreignAmount) ? foreignAmount : 0;
  },

  get_foreign_total_paid() {
    const paymentlines = this.get_order_payment_lines();
    return round_pr(
      paymentlines.reduce((sum, paymentLine) => {
        const isDone =
          typeof paymentLine?.is_done === "function"
            ? paymentLine.is_done()
            : true;
        return isDone ? sum + this.get_payment_foreign_amount(paymentLine) : sum;
      }, 0),
      this.get_foreign_rounding(),
    );
  },

  get_foreign_change(paymentline) {
    const rounding = this.get_foreign_rounding();

    if (!paymentline) {
      const change =
        this.get_foreign_total_paid() -
        this.get_foreign_total_with_taxes() -
        this.get_rounding_applied();
      return round_pr(Math.max(0, change), rounding);
    }

    const lines = this.get_order_payment_lines();

    const endIndex = lines.findIndex((line) => line === paymentline);
    const linesToSum = endIndex >= 0 ? lines.slice(0, endIndex + 1) : lines;
    const change = linesToSum.reduce(
      (sum, line) => {
        return sum + this.get_payment_foreign_amount(line);
      },
      - round_pr(this.change, rounding),
    );

    return round_pr(Math.max(0, change), rounding);
  },

  get_foreign_due(paymentline) {
    const rounding = this.get_foreign_rounding();
    const lines = this.get_order_payment_lines();

    const endIndex = lines.findIndex((line) => line === paymentline);
    const linesToSum = endIndex >= 0 ? lines.slice(0, endIndex + 1) : lines;
    const paidAmount = linesToSum.reduce(
      (sum, line) => sum + round_pr(line.foreign_amount, rounding),
      0
    );

    const totalWithTaxes = this.get_foreign_total_with_taxes();
    const due = round_pr((totalWithTaxes - paidAmount), rounding);
    console.log("DUE", due)
    return round_pr(due, rounding, "UP")
  },

  get_due_due(paymentline) {
    const rounding = this.get_foreign_rounding();
    const lines = this.get_order_payment_lines();

    const endIndex = lines.findIndex((line) => line === paymentline);
    const linesToSum = endIndex >= 0 ? lines.slice(0, endIndex + 1) : lines;
    const paidAmount = linesToSum.reduce(
      (sum, line) => sum + round_pr(line.amount, rounding),
      0
    );

    const totalWithTaxes = this.priceIncl();
    const due = round_pr((totalWithTaxes - paidAmount), rounding);
    console.log("DUE", due)
    return round_pr(due, rounding, "UP")
  },

  get_qty_products() {
    let qty = 0;
    const lines = this.get_orderlines();
    for (let i = 0; i < lines.length; i++) {
      qty += lines[i].qty;
    }
    return qty;
  },

  addPaymentline(paymentMethod) {
    const posStore = this._get_pos_store();
    if (paymentMethod.is_foreign_currency) {
        const newPaymentLine = this.models["pos.payment"].create({
              pos_order_id: this,
              payment_method_id: paymentMethod,
          });
        this.selectPaymentline(newPaymentLine);
        if (
            (paymentMethod.payment_terminal && !this.isRefund) ||
            paymentMethod.payment_method_type === "qr_code"
        ) {
            newPaymentLine.setPaymentStatus("pending");
        }
        return { status: true, data: newPaymentLine };
    }else{
      return super.addPaymentline(...arguments);
    }
  }


});
