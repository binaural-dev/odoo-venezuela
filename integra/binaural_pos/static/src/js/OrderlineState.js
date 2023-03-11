odoo.define("binaural_pos.OrderlineState", function(require) {
  "use strict";

  const { Orderline } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");

  var utils = require('web.utils');
  var round_di = utils.round_decimals;
  var round_pr = utils.round_precision;

  const BinauralOrderline = (Orderline) =>
    class BinauralOrderline extends Orderline {
      get_foreign_unit_price() {
        var digits = this.pos.dp['Product Price'];
        // round and truncate to mimic _symbol_set behavior
        return parseFloat(
          round_di((this.price || 0) *
            this.pos.config.foreign_inverse_rate,
            digits)
            .toFixed(digits));
      }
      get_all_foreign_prices(qty = this.get_quantity()) {
        var price_unit = this.get_foreign_unit_price() * (1.0 - (this.get_discount() / 100.0));
        var taxtotal = 0;

        var product = this.get_product();
        var taxes_ids = this.tax_ids || product.taxes_id;
        taxes_ids = _.filter(taxes_ids, t => t in this.pos.taxes_by_id);
        var taxdetail = {};
        var product_taxes = this.pos.get_taxes_after_fp(taxes_ids, this.order.fiscal_position);

        var all_taxes = this.compute_all(product_taxes, price_unit, qty, this.pos.foreign_currency.rounding);
        var all_taxes_before_discount = this.compute_all(product_taxes, this.get_foreign_unit_price(), qty, this.pos.foreign_currency.rounding);
        _(all_taxes.taxes).each((tax) => {
          taxtotal += tax.amount;
          taxdetail[tax.id] = tax.amount;
        });

        return {
          "priceWithTax": all_taxes.total_included,
          "priceWithoutTax": all_taxes.total_excluded,
          "priceWithTaxBeforeDiscount": all_taxes_before_discount.total_included,
          "tax": taxtotal,
          "taxDetails": taxdetail,
        };
      }

      get_foreign_tax_details(){
        return this.get_all_foreign_prices().taxDetails;
      }

      get_foreign_price_with_tax() {
        return this.get_all_foreign_prices().priceWithTax;
      }

      get_foreign_base_price() {
        var rounding = this.pos.foreign_currency.rounding;
        return round_pr(
          this.get_foreign_unit_price() *
          this.get_quantity() *
          (1 - this.get_discount() / 100),
          rounding);
      }

      get_foreign_tax() {
        return this.get_all_foreign_prices().tax;
      }
      get_foreign_price_without_tax() {
        return this.get_all_foreign_prices().priceWithoutTax;
      }
      get_display_foreign_price() {
        if (this.pos.config.iface_tax_included === 'total') {
          return this.get_foreign_price_with_tax();
        } else {
          return this.get_foreign_base_price();
        }
      }
    };
  Registries.Model.extend(Orderline, BinauralOrderline);
})
