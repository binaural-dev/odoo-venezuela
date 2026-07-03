import { PosOrderline } from "@point_of_sale/app/models/pos_order_line";
import { patch } from "@web/core/utils/patch";
import { accountTaxHelpers } from "@account/helpers/account_tax";
import {
  roundDecimals as round_di,
  roundPrecision as round_pr,
} from "@web/core/utils/numbers";

patch(PosOrderline.prototype, {
    _is_order_in_foreign_currency() {
      const foreignCurrency = this.get_foreign_currency?.();
      const orderCurrencyId = this.order_id?.currency?.id ?? this.order_id?.currency;
      const foreignCurrencyId = foreignCurrency?.id ?? foreignCurrency;
      return (
        orderCurrencyId != null &&
        foreignCurrencyId != null &&
        orderCurrencyId === foreignCurrencyId
      );
    },
    _get_effective_conversion_rate() {
      const fromOrder = Number(this.order_id?.get_conversion_rate?.());
      if (Number.isFinite(fromOrder) && fromOrder > 0) {
        return fromOrder;
      }

      if (!this.order_id?._invalidConversionRateWarningShown) {
        this.order_id._invalidConversionRateWarningShown = true;
        console.warn(
          "[l10n_ve_pos] Invalid conversion rate on order; foreign amount calculations are disabled for this line.",
          { conversionRate: this.order_id?.get_conversion_rate?.() }
        );
      }

      return 0;
    },
    _get_foreign_currency_rounding() {
      const foreignCurrency = this.get_foreign_currency?.();
      const rounding = Number(foreignCurrency?.rounding);
      return Number.isFinite(rounding) && rounding > 0 ? rounding : 0.01;
    },
    _get_foreign_currency_decimals() {
      const foreignCurrency = this.get_foreign_currency?.();
      const decimals = Number(foreignCurrency?.decimal_places);
      return Number.isInteger(decimals) && decimals >= 0 ? decimals : 2;
    },

    _get_raw_foreign_unit_price() {
      const baseUnitPrice = Number(this.price_unit || 0);
      if (!Number.isFinite(baseUnitPrice) || baseUnitPrice <= 0) {
        return 0;
      }

      if (this._is_order_in_foreign_currency()) {
        return baseUnitPrice;
      }

      const conversionRate = this._get_effective_conversion_rate();
      if (!Number.isFinite(conversionRate) || conversionRate <= 0) {
        return 0;
      }

      return conversionRate > 1
        ? baseUnitPrice / conversionRate
        : baseUnitPrice * conversionRate;
    },
    setUnitPrice(price) {
      super.setUnitPrice(...arguments);
      const digits = this._get_foreign_currency_decimals();

      if (this._is_order_in_foreign_currency()) {
        this.foreign_price = parseFloat(
          round_di(this.price_unit || 0, digits).toFixed(digits),
        );
        return;
      }

      const conversionRate = this._get_effective_conversion_rate();
      if (!Number.isFinite(conversionRate) || conversionRate <= 0) {
        return;
      }

      const foreignUnitPrice = conversionRate > 1
        ? (this.price_unit || 0) / conversionRate
        : (this.price_unit || 0) * conversionRate;

      // Keep raw precision for arithmetic. UI formatting will round using
      // foreign currency settings.
      this.foreign_price = foreignUnitPrice;
    },
    get_foreign_currency(){
        return this.config.foreign_currency_id;
    },
    get_foreign_price_without_tax() {
    const digits = this._get_foreign_currency_rounding();
    const rawForeignUnitPrice = this._get_raw_foreign_unit_price();
    return round_pr(
      rawForeignUnitPrice * this.getQuantity(),
      digits
    );
    },
    get_foreign_tax_details() {
    return this.get_all_foreign_prices().taxDetails;
    },
    get_foreign_price_with_tax() {
      const allPrices = this.get_all_foreign_prices?.();
      const computed = Number(allPrices?.priceWithTax);
      if (Number.isFinite(computed) && computed > 0) {
        return computed;
      }
      return this.get_foreign_price_without_tax() + this.get_foreign_total_tax();

    },
    get_foreign_total_tax() {
      const allPrices = this.get_all_foreign_prices?.();
      const taxFromAllPrices = Number(allPrices?.tax);
      if (Number.isFinite(taxFromAllPrices)) {
        const digits = this._get_foreign_currency_rounding();
        return round_pr(taxFromAllPrices, digits);
      }
      return 0;
    },
    // get_foreign_price_without_tax() {
    //   return this.get_all_foreign_prices().priceWithoutTax;
    // },

    get_foreign_unit_price() {
      const digits = this._get_foreign_currency_decimals();
      const hasStoredForeignPrice = this.foreign_price !== undefined && this.foreign_price !== null;
      const storedForeignPrice = Number(this.foreign_price);
      if (hasStoredForeignPrice && Number.isFinite(storedForeignPrice) && storedForeignPrice > 0) {
        return parseFloat(
          round_di(storedForeignPrice, digits).toFixed(digits),
        );
      }

      const baseUnitPrice = Number(this.price_unit || 0);
      if (!Number.isFinite(baseUnitPrice) || baseUnitPrice <= 0) {
        return 0;
      }
      const foreignUnitPrice = this._get_raw_foreign_unit_price();
      return parseFloat(
        round_di(foreignUnitPrice, digits).toFixed(digits),
      );
    },

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
                price_unit: this._get_raw_foreign_unit_price(), // <--- precio foráneo SIN redondeo temprano
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
                price_unit: this._get_raw_foreign_unit_price(), // <--- precio foráneo SIN redondeo temprano
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
})  ;
