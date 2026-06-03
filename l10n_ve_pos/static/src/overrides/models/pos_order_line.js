import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { patch } from "@web/core/utils/patch";
import { accountTaxHelpers } from "@account/helpers/account_tax";
import {
  formatFloat,
  roundDecimals as round_di,
  roundPrecision as round_pr,
  floatIsZero,
} from "@web/core/utils/numbers";


patch(PosOrderline.prototype, {

  setup() {
    super.setup(...arguments);
  },

  get_foreign_currency() {
    return this.config.foreign_currency_id;
  },

  get price_unit_with_taxes_raw() {
    return this.unitPrices?.raw_total_included_currency || 0;
  },

  get price_unit_with_taxes() {
    const raw = this.price_unit_with_taxes_raw;
    if (this.currency?.round) {
      return this.currency.round(raw);
    }
    return round_pr(raw, this.currency?.rounding || 0.01, "UP");
  },

  get foreign_subtotal_display() {
    return this.get_all_foreign_prices();
  },

  get_foreign_price_without_tax() {
    if (!this.get_all_foreign_prices) {
      return 0;
    }
    return this.get_all_foreign_prices().priceWithoutTax || 0;
  },

  get_foreign_tax_details() {
    return this.get_all_foreign_prices().taxDetails;
  },

  get_foreign_price_with_tax() {
    return this.get_all_foreign_prices().priceWithTax;

  },

  get_foreign_total_tax() {
    return this.get_all_foreign_prices().tax || 0;
  },

  get_rate(currency) {
    if (this.refunded_orderline_id && this.refunded_orderline_id.foreign_currency_rate) {
      return this.refunded_orderline_id.foreign_currency_rate;
    }
    return currency.rate;
  },

  get_foreign_unit_price() {

    const foreign_currency = this.get_foreign_currency()
    const unitPrice = Number(this.price_unit || 0);
    const price = this.get_foreign_calculation_price(foreign_currency, unitPrice)
    this.foreign_price_unit = price
    return this.foreign_price_unit;

  },

  /**get_all_foreign_prices
   * This function returns the total price of the product in the foreign currency.
   * @param {number} qty - product_qty equals actual getter of the product.
   */
  get_all_foreign_prices(qty = this.getQuantity()) {
    const company = this.company;
    const product = this.getProduct();
    const taxes = this.tax_ids || product.taxes_id;
    // Usar el precio unitario foráneo y la moneda foránea
    const baseLine = accountTaxHelpers.prepare_base_line_for_taxes_computation(
      this,
      this.prepareBaseLineForTaxesComputationExtraValues({
        quantity: qty,
        tax_ids: taxes,
        price_unit: this.get_foreign_unit_price(), // <--- precio foráneo
        currency: this.get_foreign_currency(),     // <--- moneda foránea
      })
    );
    accountTaxHelpers.add_tax_details_in_base_line(baseLine, company);
    accountTaxHelpers.round_base_lines_tax_details([baseLine], company);

    // Sin descuento
    const baseLineNoDiscount = accountTaxHelpers.prepare_base_line_for_taxes_computation(
      this,
      this.prepareBaseLineForTaxesComputationExtraValues({
        quantity: qty,
        tax_ids: taxes,
        discount: 0.0,
        price_unit: this.get_foreign_unit_price(), // <--- precio foráneo
        currency: this.get_foreign_currency(),     // <--- moneda foránea
      })
    );
    accountTaxHelpers.add_tax_details_in_base_line(baseLineNoDiscount, company);
    accountTaxHelpers.round_base_lines_tax_details([baseLineNoDiscount], company);
    
    // Tax details.
    const taxDetails = {};
    for (const taxData of baseLine.tax_details.taxes_data) {
      taxDetails[taxData.tax.id] = {
        amount: taxData.tax_amount_currency,
        base: taxData.base_amount_currency,
      };
    }
    return {
      priceWithTax: baseLine.tax_details.total_included_currency,
      priceWithoutTax: baseLine.tax_details.total_excluded_currency,
      priceWithTaxBeforeDiscount: baseLineNoDiscount.tax_details.total_included_currency,
      priceWithoutTaxBeforeDiscount: baseLineNoDiscount.tax_details.total_excluded_currency,
      tax:
        baseLine.tax_details.total_included_currency -
        baseLine.tax_details.total_excluded_currency,
      taxDetails: taxDetails,
      taxesData: baseLine.tax_details.taxes_data,
    };
  },

 get_foreign_calculation_price(currency, price) {
    const rate = this.get_rate(currency);
    const amount = price * rate;
    return amount   
  },

});