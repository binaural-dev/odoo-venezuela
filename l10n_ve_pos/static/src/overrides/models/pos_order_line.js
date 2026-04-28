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
    this.get_all_foreign_prices()
    super.setup(...arguments);
  },

  get_foreign_currency() {
    return this.config.foreign_currency_id;
  },

  get foreign_subtotal_display() {
    return this.get_all_foreign_prices();
  },

  get_foreign_price_without_tax() {
    if (!this.get_foreign_unit_price) {
    }

    const digits = 2;
    return round_pr(
      this.get_foreign_unit_price() * this.getQuantity(),
      digits
    );
  },

  get_foreign_tax_details() {
    return this.get_all_foreign_prices().taxDetails;
  },

  get_foreign_price_with_tax() {
    return this.get_all_foreign_prices().priceWithTax;

  },

  get_foreign_total_tax() {
    return round_pr(
      this.get_foreign_price_without_tax() * (this.get_tax() / 100),
      this.foreign_currency.rounding,
    );
  },


  get_rate(currency) {
    const inverse_rate = currency.rate;
    return inverse_rate.toFixed(6);
  },

  get_foreign_unit_price() {

    const foreign_currency = this.get_foreign_currency()
    const price = this.get_foreign_calculation_price(foreign_currency, this.price_unit.toFixed(6))
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
    return parseFloat((price * rate).toFixed(6));
  },

  get foreign_price_unit_display() {
    return this.get_all_foreign_prices().priceWithTax;
  },


});