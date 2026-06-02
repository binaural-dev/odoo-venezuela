import { patch } from "@web/core/utils/patch";
import { Orderline } from "@point_of_sale/app/components/orderline/orderline";
import { onWillUpdateProps, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
patch(Orderline.prototype, {
  setup() {
    super.setup(...arguments);
    this.orm = useService("orm");
    this.state = useState({ foreign_price_unit_display_server: 0 });
    this._lastReqId = 0;

    onWillStart(async () => {
      await this._syncForeignPriceUnitDisplay(this.props?.line);
    });

    onWillUpdateProps(async (nextProps) => {
      await this._syncForeignPriceUnitDisplay(nextProps?.line);
    });
  },

  get_rate() {
    if (this.order.isRefund && this.refunded_orderline_id) {
      return this.refunded_orderline_id.foreign_currency_rate;
    }
    if (
      this.foreign_currency_rate &&
      this.foreign_currency_rate != this.order.init_conversion_rate
    )
      return this.foreign_currency_rate;

    return this.order.init_conversion_rate;
  },


  set set_unit_price(price) {
    this.order.assert_editable();
    var parsed_price = !isNaN(price)
      ? price
      : isNaN(parseFloat(price))
        ? 0
        : parseFloat("" + price);
    this.price = round_di(
      parsed_price || 0,
      this.pos.dp["Foreign Product Price"],
    );
    this.foreign_price = parsed_price * this.get_rate() || 0;
  },

  set_foreign_unit_price(price) {
    this.order.assert_editable();
    var parsed_price = !isNaN(price)
      ? price
      : isNaN(parseFloat(price))
        ? 0
        : parseFloat("" + price);
    this.foreign_price = parsed_price * this.get_rate() || 0;
  },

  getPriceWithOptions() {
    return super.getPriceWithOptions();
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

  get foreign_price_unit_display() {
    return this.state.foreign_price_unit_display_server;
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


  async _syncForeignPriceUnitDisplay(line) {

    const amount = Number(
      line?.price_unit_with_taxes ??
      line?.get_price_with_tax?.() ??
      line?.price_unit ??
      0
    );

    if (!Number.isFinite(amount)) {
      this.state.foreign_price_unit_display_server = 0;
      return;
    }
    const reqId = ++this._lastReqId;
    try {
      const converted = await this.orm.call(
        "pos.order.line",
        "convert_amount",
        [amount],
        { context: { amount } }
      );
      console.log("Converted amount from server:", converted);
      if (reqId === this._lastReqId) {
        const qty = Number(line?.qty ?? line?.qty ?? 1);
        this.state.foreign_price_unit_display_server =
          Number(converted || 0) * (Number.isFinite(qty) ? qty : 1);
      }
    } catch {
      if (reqId === this._lastReqId) {
        const rate = Number(this.pos?.foreign_currency?.rate || 1);
        this.state.foreign_price_unit_display_server = amount * rate;
      }
    }
  },



});
