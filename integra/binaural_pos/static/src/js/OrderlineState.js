odoo.define("binaural_pos.OrderlineState", function(require) {
  "use strict";

  const { Orderline } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");

  var utils = require('web.utils');
  var round_di = utils.round_decimals;
  var round_pr = utils.round_precision;

  const BinauralOrderline = (Orderline) =>
    class BinauralOrderline extends Orderline {
      constructor(data, options) {
        super(...arguments)
        this.order.toggle_receipt_invoice(this.order.to_receipt)
        this.foreign_currency_rate = options.order.foreign_currency_rate || this.pos.config.foreign_rate
      }
      set_foreign_currency_rate(rate) {
        this.foreign_currency_rate = rate
      }
      init_from_JSON(json) {
        super.init_from_JSON(...arguments)
        this.foreign_currency_rate = json.foreign_currency_rate
      }

      export_as_JSON() {
        let res = super.export_as_JSON()
        res["foreign_currency_rate"] = this.foreign_currency_rate
        return res 
      }
      isExempt() {
        const product_tax = this.tax_ids || this.product.taxes_id;
        if (product_tax.length < 1) {
          return true
        }
        const tax = this.pos.taxes_by_id[product_tax[0]];
        if (tax.amount === 0) {
          return true
        }
        return false
      }
      get_foreign_unit_price() {
        var digits = this.pos.dp['Product Price'];
        // round and truncate to mimic _symbol_set behavior
        return parseFloat(
          round_di((this.price || 0) *
            this.foreign_currency_rate,
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

      get_foreign_tax_details() {
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
