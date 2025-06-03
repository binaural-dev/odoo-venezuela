/** @odoo-module */

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import {
  formatFloat,
  roundDecimals as round_di,
  roundPrecision as round_pr,
  floatIsZero,
} from "@web/core/utils/numbers";
import { _t } from "@web/core/l10n/translation";

// New orders are now associated with the current table, if any.
patch(Order.prototype, {
  setup(_defaultObj, options) {
    super.setup(...arguments);
    this.set_to_invoice(true);
    if (options.json) {
      if (options.json.account_move === undefined) {
        this.set_to_invoice(true);
        this.lock_toggle_receipt_invoice = false;
      }
      this.reload_taxes();
    } else {
      let always_invoice = !this.pos.config.always_invoice;
      this.to_receipt = always_invoice;
    }
  },
  _isValidEmptyOrder() {
    let res = super._isValidEmptyOrder(...arguments);
    if (this.get_change() != 0) {
      return false;
    }
    return res;
  },
  assert_editable() {},
  get init_conversion_rate() {
    //FIXME :Buscar una manera de esto sea por id y no por name
    if (this.pos.currency.name == "VEF") {
      return this.pos.config.foreign_inverse_rate;
    }
    if (this.pos.currency.name == "USD") {
      return this.pos.config.foreign_rate;
    }
  },
  get_display_rate() {
    return this.pos.config.foreign_rate;
  },

  add_orderline(line) {
    let res = super.add_orderline(...arguments);
    this.reload_taxes();
    return res;
  },
  get_conversion_rate() {
    if (this.orderlines.length != 0) {
      return this.orderlines[0].currency_rate_display();
    }
    if (!this.init_conversion_rate) {
      throw new Error(
        "Conversion rate cannot be determined due to missing values.",
      );
    }

    return this.init_conversion_rate;
  },

  // get_orderlines() {
  //   if (!this.cid || !this.pos.get_order()) {
  //     return this.orderlines
  //   }

  //   if (this.cid != this.pos.get_order().cid) {
  //     return this.orderlines;
  //   }

  //   if (this.orderlines.length < 1) {
  //     this.lock_toggle_receipt_invoice = false
  //     return this.orderlines
  //   }

  //   let line = this.orderlines[0]

  //   if (!line.refunded_orderline_id) {
  //     return this.orderlines
  //   }

  //   if (this.lock_toggle_receipt_invoice) {
  //     return this.orderlines
  //   }

  //   this.pos.env.services.rpc({
  //     model: 'pos.order.line',
  //     method: 'search_read',
  //     domain: [['id', '=', line.refunded_orderline_id]],
  //   }).then((el) => {
  //     this.to_receipt = el[0].to_receipt
  //     this.lock_toggle_receipt_invoice = true
  //   })

  //   return this.orderlines;
  // },

  reload_taxes() {
    this.orderlines.forEach((el) => {
      el.product.taxes_id = el.product.originalTaxes;
      el.tax_ids = el.product.taxes_id;
    });
  },
  toggle_receipt_invoice(to_receipt) {
    if (this.getHasRefundLines()) {
      return;
    }
    if (this.lock_toggle_receipt_invoice) {
      return;
    }
    this.assert_editable();
    this.to_receipt = to_receipt;
    this.reload_taxes();
  },
  export_as_JSON() {
    let json = super.export_as_JSON();
    json["foreign_amount_total"] = this.get_foreign_total_with_tax();
    json["foreign_currency_rate"] = this.get_conversion_rate();
    json["to_receipt"] = this.is_to_receipt();
    return json;
  },
  is_to_receipt() {
    return this.to_receipt;
  },
  export_for_printing() {
    let res = super.export_for_printing(...arguments);
    let new_res = {
      ...res,
      foreign_amount_total: this.get_foreign_total_with_tax(),
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
  get_foreign_total_with_tax() {
    return this.get_foreign_total_without_tax() + this.get_foreign_total_tax();
  },
  get_foreign_total_without_tax() {
    return round_pr(
      this.orderlines.reduce(function (sum, orderLine) {
        return sum + orderLine.get_foreign_price_without_tax();
      }, 0),
      this.pos.foreign_currency.rounding,
    );
  },
  get_foreign_total_discount() {
    const ignored_product_ids = this._get_ignored_product_ids_total_discount();
    return round_pr(
      this.orderlines.reduce((sum, orderLine) => {
        if (!ignored_product_ids.includes(orderLine.product.id)) {
          sum +=
            orderLine.getForeignUnitDisplayPriceBeforeDiscount() *
            (orderLine.get_discount() / 100) *
            orderLine.get_quantity();
          if (orderLine.display_discount_policy() === "without_discount") {
            sum +=
              (orderLine.get_taxed_lst_unit_foreign_price() -
                orderLine.getForeignUnitDisplayPriceBeforeDiscount()) *
              orderLine.get_quantity();
          }
        }
        return sum;
      }, 0),
      this.pos.foreign_currency.rounding,
    );
  },
  get_foreign_total_tax() {
    if (this.pos.company.tax_calculation_rounding_method === "round_globally") {
      // As always, we need:
      // 1. For each tax, sum their amount across all order lines
      // 2. Round that result
      // 3. Sum all those rounded amounts
      var groupTaxes = {};
      this.orderlines.forEach(function (line) {
        var taxDetails = line.get_foreign_tax_details();
        var taxIds = Object.keys(taxDetails);
        for (var t = 0; t < taxIds.length; t++) {
          var taxId = taxIds[t];
          if (!(taxId in groupTaxes)) {
            groupTaxes[taxId] = 0;
          }
          groupTaxes[taxId] += taxDetails[taxId].amount;
        }
      });

      var sum = 0;
      var taxIds = Object.keys(groupTaxes);
      for (var j = 0; j < taxIds.length; j++) {
        var taxAmount = groupTaxes[taxIds[j]];
        sum += round_pr(taxAmount, this.pos.foreign_currency.rounding);
      }
      return sum;
    } else {
      return round_pr(
        this.orderlines.reduce(function (sum, orderLine) {
          return sum + orderLine.get_foreign_tax();
        }, 0),
        this.pos.foreign_currency.rounding,
      );
    }
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
      var taxes_ids = this.tax_ids || line.get_product().taxes_id;
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

    if (order.getHasRefundLines()) {
      return await super.pay();
    }
    await this.pos.update_products(order);

    if (this.pos.config.amount_to_zero) {
      let product_quantity_by_product = {};
      let products = [];
      for (let line of lines) {
        let prd = this.pos.db.get_product_by_id(line.get_product().id);

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
    if (this.pos.config.cash_rounding) {
      const only_cash = this.pos.config.only_round_cash_method;
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
          this.get_foreign_total_with_tax() - this.get_total_paid();
        var sign = this.get_foreign_total_with_tax() > 0 ? 1.0 : -1.0;
        if (
          ((this.get_foreign_total_with_tax() < 0 && remaining > 0) ||
            (this.get_foreign_total_with_tax() > 0 && remaining < 0)) &&
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
          Math.abs(this.get_foreign_total_with_tax()) <
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

  get_foreign_total_paid() {
    return round_pr(
      this.paymentlines.reduce(function (sum, paymentLine) {
        if (paymentLine.is_done()) {
          sum += paymentLine.get_foreign_amount();
        }
        return sum;
      }, 0),
      this.pos.foreign_currency.rounding,
    );
  },
  get_foreign_change(paymentline) {
    if (!paymentline) {
      var change =
        this.get_foreign_total_paid() -
        this.get_foreign_total_with_tax() -
        this.get_rounding_applied();
    } else {
      change = -this.get_foreign_total_with_tax();
      var lines = this.paymentlines;
      for (var i = 0; i < lines.length; i++) {
        change += lines[i].get_foreign_amount();
        if (lines[i] === paymentline) {
          break;
        }
      }
    }
    return round_pr(Math.max(0, change), this.pos.foreign_currency.rounding);
  },
  get_foreign_due(paymentline) {
    if (!paymentline) {
      var due =
        this.get_foreign_total_with_tax() -
        this.get_foreign_total_paid() +
        this.get_rounding_applied();
    } else {
      due = this.get_foreign_total_with_tax();
      var lines = this.paymentlines;
      for (var i = 0; i < lines.length; i++) {
        if (lines[i] === paymentline) {
          break;
        } else {
          due -= lines[i].get_foreign_amount();
        }
      }
    }
    return round_pr(due, this.pos.foreign_currency.rounding);
  },

  get_qty_products() {
    let quantity = 0;
    this.get_orderlines().forEach((line) => {
      quantity += line.quantity;
    });
    return quantity;
  },
});
