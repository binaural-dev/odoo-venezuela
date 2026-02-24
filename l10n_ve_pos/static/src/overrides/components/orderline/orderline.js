
patch(Orderline.prototype, {
  //DEPRECATED
  // init_from_JSON(json) {
  //   super.init_from_JSON(...arguments);
  //   this.tax_ids =
  //     json.tax_ids && json.tax_ids.length !== 0
  //       ? json.tax_ids[0][2]
  //       : undefined;
  //   this.foreign_price = json.foreign_price || 0;
  //   this.foreign_currency_rate = json.foreign_currency_rate || false;
  //   this.foreign_currency_rate_display = false;
  // },
  setup() {
    super.setup();
  },
  get_rate() {
    if (this.order._isRefundOrder() && this.get_refund_orderline()) {
      return this.get_refund_orderline().orderline.foreign_currency_rate;
    }

    if (
      this.foreign_currency_rate &&
      this.foreign_currency_rate != this.order.init_conversion_rate
    )
      return this.foreign_currency_rate;

    return this.order.init_conversion_rate;
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
  // export_as_JSON() {
  //   let res = super.export_as_JSON(...arguments);
  //   res["foreign_currency_rate"] = this.get_rate();
  //   res["foreign_price"] = this.get_foreign_unit_price();
  //   res["foreign_price_subtotal"] = this.get_foreign_price_without_tax();
  //   res["foreign_price_subtotal_incl"] = this.get_foreign_price_with_tax();
  //   return res;
  // },
  set_unit_price(price) {
    this.order.assert_editable();
    var parsed_price = !isNaN(price)
      ? price
      : isNaN(parseFloat(price))
        ? 0
        : oParseFloat("" + price);
    this.price = round_di(
      parsed_price || 0,
      this.pos.dp["Foreign Product Price"],
    );
    this.foreign_price = round_di(
      parsed_price * this.get_rate() || 0,
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

  

  get_all_prices(qty = this.getQuantity()) {
    return super.get_all_prices(qty);
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
    const product = this.getProduct();
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
