/** @odoo-module */

import { Orderline } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import {
  formatFloat,
  floatIsZero,
  roundDecimals as round_di,
  roundPrecision as round_pr,
} from "@web/core/utils/numbers";

// New orders are now associated with the current table, if any.
patch(Orderline.prototype, {
  init_from_JSON(json) {
    super.init_from_JSON(...arguments);
    this.tax_ids =
      json.tax_ids && json.tax_ids.length !== 0
        ? json.tax_ids[0][2]
        : undefined;
    this.foreign_price = json.foreign_price || 0;
    this.foreign_currency_rate = json.foreign_currency_rate || false;
    this.foreign_currency_rate_display = false;
  },
  get_rate() {
    let rate = 0;
    if (this.order._isRefundOrder() && this.get_refund_orderline()) {
      rate = this.get_refund_orderline().orderline.foreign_currency_rate;
    } else if (
      this.foreign_currency_rate &&
      this.foreign_currency_rate != this.order.init_conversion_rate
    ) {
      rate = this.foreign_currency_rate;
    } else {
      rate = this.order.init_conversion_rate;
    }

    let decimal_places =
      this.pos.currency.name === "VEF"
        ? this.pos.currency.decimal_places
        : this.pos.foreign_currency.decimal_places;

    return round_di(rate, decimal_places);
  },
  get currency_rate_display() {
    return this.order.get_display_rate;
  },
  get_refund_orderline() {
    for (let id of Object.keys(this.pos.toRefundLines)) {
      if (this.refunded_orderline_id == id) {
        return this.pos.toRefundLines[id];
      }
    }
    return false;
  },
  export_as_JSON() {
    let res = super.export_as_JSON(...arguments);
    res["foreign_currency_rate"] = this.get_rate();
    res["foreign_price"] = this.get_foreign_unit_price();
    res["foreign_price_subtotal"] = this.get_foreign_price_without_tax();
    res["foreign_price_subtotal_incl"] = this.get_foreign_price_with_tax();
    return res;
  },
  set_unit_price(price) {
    super.set_unit_price(price);
    this.foreign_price = round_di(
      this.get_unit_price() * this.get_rate() || 0,
      this.pos.dp["Foreign Product Price"],
    );
  },

  set_foreign_unit_price(price) {
    this.order.assert_editable();
    var parsed_price = !isNaN(price)
      ? price
      : isNaN(parseFloat(price))
        ? 0
        : oParseFloat("" + price);
    this.foreign_price = round_di(
      parsed_price || 0,
      this.pos.dp["Foreign Product Price"],
    );
  },

  get_foreign_unit_price() {
    var digits = this.pos.dp["Foreign Product Price"];
    // round and truncate to mimic _symbol_set behavior
    return parseFloat(
      round_di(this.foreign_price || 0, digits).toFixed(digits),
    );
  },

  get_all_prices(qty = this.get_quantity()) {
    return super.get_all_prices(qty);
  },

  get_all_foreign_prices(qty = this.get_quantity()) {
    var price_unit =
      this.get_foreign_unit_price() * (1.0 - this.get_discount() / 100.0);
    var taxtotal = 0;

    var product = this.get_product();
    var taxes_ids = this.tax_ids || product.taxes_id;
    taxes_ids = taxes_ids.filter((t) => t in this.pos.taxes_by_id);
    var taxdetail = {};
    var product_taxes = this.pos.get_taxes_after_fp(
      taxes_ids,
      this.order.fiscal_position,
    );

    var all_taxes = this.compute_all(
      product_taxes,
      round_pr(price_unit, this.pos.foreign_currency.rounding),
      qty,
      this.pos.foreign_currency.rounding,
    );
    var all_taxes_before_discount = this.compute_all(
      product_taxes,
      this.get_foreign_unit_price(),
      qty,
      this.pos.foreign_currency.rounding,
    );
    all_taxes.taxes.forEach(function (tax) {
      taxtotal += tax.amount;
      taxdetail[tax.id] = {
        amount: tax.amount,
        base: tax.base,
      };
    });
    console.log("pricewithtax", all_taxes.total_included)
    console.log("price without tax", all_taxes.total_excluded)
    console.log("taxdetails", taxdetail)
    return {
      priceWithTax: all_taxes.total_included,
      priceWithoutTax: all_taxes.total_excluded,
      priceWithTaxBeforeDiscount: all_taxes_before_discount.total_included,
      priceWithoutTaxBeforeDiscount: all_taxes_before_discount.total_excluded,
      tax: taxtotal,
      taxDetails: taxdetail,
    };
  },

  get_foreign_price_without_tax() {
    return this.get_all_foreign_prices().priceWithoutTax;
  },
  get_foreign_price_with_tax() {
    return this.get_all_foreign_prices().priceWithTax;
  },
  get_foreign_price_with_tax_before_discount() {
    return this.get_all_foreign_prices().priceWithTaxBeforeDiscount;
  },
  get_foreign_tax() {
    return this.get_all_foreign_prices().tax;
  },

  get_display_foreign_price() {
    if (this.pos.config.iface_tax_included === "total") {
      return this.get_foreign_price_with_tax();
    } else {
      return this.get_foreign_price_without_tax();
    }
  },
  get_unit_display_foreign_price() {
    if (this.pos.config.iface_tax_included === "total") {
      return this.get_all_foreign_prices(1).priceWithTax;
    } else {
      return this.get_all_foreign_prices(1).priceWithoutTax;
    }
  },

  get_foreign_tax_details() {
    return this.get_all_foreign_prices().taxDetails;
  },

  get_foreign_total_taxes_included_in_price() {
    const productTaxes = this._getProductTaxesAfterFiscalPosition();
    const taxDetails = this.get_foreign_tax_details();
    return productTaxes
      .filter((tax) => tax.price_include)
      .reduce((sum, tax) => sum + taxDetails[tax.id].amount, 0);
  },

  getForeignUnitDisplayPriceBeforeDiscount() {
    if (this.pos.config.iface_tax_included === "total") {
      return this.get_all_foreign_prices(1).priceWithTaxBeforeDiscount;
    } else {
      return this.get_all_foreign_prices(1).priceWithoutTaxBeforeDiscount;
    }
  },

  get_lst_foreign_price() {
    return this.product.get_foreign_price(
      this.pos.default_pricelist,
      1,
      this.price_extra,
    );
  },

  get_taxed_lst_unit_foreign_price() {
    const lstPrice = this.compute_fixed_price(this.get_lst_foreign_price());
    const product = this.get_product();
    const taxesIds = product.taxes_id;
    const productTaxes = this.pos.get_taxes_after_fp(
      taxesIds,
      this.order.fiscal_position,
    );
    const unitPrices = this.compute_all(
      productTaxes,
      lstPrice,
      1,
      this.pos.foreign_currency.rounding,
    );
    if (this.pos.config.iface_tax_included === "total") {
      return unitPrices.total_included;
    } else {
      return unitPrices.total_excluded;
    }
  },

  get_aliquot_type() {
    const product_tax = this.tax_ids || this.product.taxes_id;
    if (product_tax.length < 1) {
      return "(E)";
    }
    const tax = this.pos.taxes_by_id[product_tax[0]];
    if (tax.amount === 0) {
      return "(E)";
    }
    return "(G)";
  },

  getDisplayData() {
    let res = super.getDisplayData(...arguments);
    res["foreignUnitPrice"] = this.env.utils.formatForeignCurrency(
      this.get_unit_display_foreign_price(),
    );
    res["foreignPrice"] =
      this.get_discount_str() === "100"
        ? "free"
        : this.env.utils.formatForeignCurrency(
          this.get_display_foreign_price(),
        );
    res["aliquot_type"] = this.get_aliquot_type();
    res["foreign_currency_rate"] = this.get_rate();
    res["foreign_currency_rate_display"] = this.env.utils.formatForeignCurrency(
      this.currency_rate_display(),
    );
    return res;
  },
});
