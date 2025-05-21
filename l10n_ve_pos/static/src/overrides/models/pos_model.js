/** @odoo-module **/

import { PosStore } from "@point_of_sale/app/store/pos_store";
import { patch } from "@web/core/utils/patch";
import { roundPrecision as round_pr, floatIsZero } from "@web/core/utils/numbers";

patch(PosStore.prototype, {

  //@override
  async _processData(loadedData) {
    await super._processData(loadedData);
    this.currency = loadedData["res.currency"][0];
    this.foreign_currency = loadedData["res.currency"][1];
    this.cities = loadedData["res.country.city"];
    this.prefix_vats = loadedData["prefix_vats"];
  },
  async push_orders(order, opts) {
    let res = await super.push_orders(order, opts);
    await this.update_products(order)
    return res
  },
  async push_single_order(order, opts) {
    let res = await super.push_single_order(...arguments);
    await this.update_products(order)
    return res
  },
  async update_products(order) {
    if (!order || !order.cid) {
      return
    }
    let product_ids = []
    order.orderlines.forEach(line => {
      if (line.product.id in product_ids) {
        return
      }
      product_ids.push(line.product.id)
    })
    try{
      const products = await this.orm.silent.call('pos.session', 'get_pos_ui_product_product_by_params', [odoo.pos_session_id, { domain: [['id', 'in', product_ids]] }],
      );
      this._loadProductProduct(products);
    }catch(e){
      console.warn("Error while updating products", e)
    }

  },
  compute_all(taxes, price_unit, quantity, currency_rounding, handle_price_include = true) {
    var self = this;

    // 1) Flatten the taxes.

    var _collect_taxes = function(taxes, all_taxes) {
      taxes = [...taxes].sort(function(tax1, tax2) {
        return tax1.sequence - tax2.sequence;
      });
      taxes.forEach((tax) => {
        if (tax.amount_type === "group") {
          all_taxes = _collect_taxes(tax.children_tax_ids, all_taxes);
        } else {
          all_taxes.push(tax);
        }
      });
      return all_taxes;
    };
    var collect_taxes = function(taxes) {
      return _collect_taxes(taxes, []);
    };

    taxes = collect_taxes(taxes);

    // 2) Deal with the rounding methods

    const company = this.company;
    var round_tax = company.tax_calculation_rounding_method != "round_globally";

    var initial_currency_rounding = currency_rounding;
    if (!round_tax) {
      currency_rounding = currency_rounding * 0.00001;
    }

    // 3) Iterate the taxes in the reversed sequence order to retrieve the initial base of the computation.
    var recompute_base = function(base_amount, incl_tax_amounts) {
      let fixed_amount = incl_tax_amounts.fixed_amount;
      let division_amount = 0.0;
      for (const [, tax_factor] of incl_tax_amounts.division_taxes) {
        division_amount += tax_factor;
      }
      let percent_amount = 0.0;
      for (const [, tax_factor] of incl_tax_amounts.percent_taxes) {
        percent_amount += tax_factor;
      }

      if (company.country && company.country.code === "IN") {
        let total_tax_amount = 0.0;
        for (const [i, tax_factor] of incl_tax_amounts.percent_taxes) {
          const tax_amount = round_pr(base_amount * tax_factor / (100 + percent_amount), currency_rounding);
          total_tax_amount += tax_amount;
          cached_tax_amounts[i] = tax_amount;
          fixed_amount += tax_amount;
        }
        for (const [i,] of incl_tax_amounts.percent_taxes) {
          cached_base_amounts[i] = base - total_tax_amount;
        }
        percent_amount = 0.0;
      }

      Object.assign(incl_tax_amounts, {
        percent_taxes: [],
        division_taxes: [],
        fixed_amount: 0.0,
      });

      return (
        (((base_amount - fixed_amount) / (1.0 + percent_amount / 100.0)) *
          (100 - division_amount)) /
        100
      );
    };

    var base = round_pr(price_unit * quantity, initial_currency_rounding);

    var sign = 1;
    if (base < 0) {
      base = -base;
      sign = -1;
    }

    var total_included_checkpoints = {};
    var i = taxes.length - 1;
    var store_included_tax_total = true;

    const incl_tax_amounts = {
      percent_taxes: [],
      division_taxes: [],
      fixed_amount: 0.0,
    };

    var cached_tax_amounts = {};
    var cached_base_amounts = {};
    let is_base_affected = true;
    if (handle_price_include) {
      taxes.reverse().forEach(function(tax) {
        if (tax.include_base_amount && is_base_affected) {
          base = recompute_base(base, incl_tax_amounts);
          store_included_tax_total = true;
        }
        if (tax.price_include) {
          if (tax.amount_type === "percent") {
            incl_tax_amounts.percent_taxes.push([
              i,
              tax.amount * tax.sum_repartition_factor,
            ]);
          } else if (tax.amount_type === "division") {
            incl_tax_amounts.division_taxes.push([
              i,
              tax.amount * tax.sum_repartition_factor,
            ]);
          } else if (tax.amount_type === "fixed") {
            incl_tax_amounts.fixed_amount +=
              Math.abs(quantity) * tax.amount * tax.sum_repartition_factor;
          } else {
            var tax_amount = self._compute_all(tax, base, quantity);
            incl_tax_amounts.fixed_amount += tax_amount;
            cached_tax_amounts[i] = tax_amount;
          }
          if (store_included_tax_total) {
            total_included_checkpoints[i] = base;
            store_included_tax_total = false;
          }
        }
        i -= 1;
        is_base_affected = tax.is_base_affected;
      });
    }

    var total_excluded = round_pr(
      recompute_base(base, incl_tax_amounts),
      initial_currency_rounding
    );
    var total_included = total_excluded;

    // 4) Iterate the taxes in the sequence order to fill missing base/amount values.

    base = total_excluded;

    var skip_checkpoint = false;

    var taxes_vals = [];
    i = 0;
    var cumulated_tax_included_amount = 0;
    taxes.reverse().forEach(function(tax) {
      if (tax.price_include && i in cached_base_amounts) {
        var tax_base_amount = cached_base_amounts[i];
      } else if (tax.price_include || tax.is_base_affected) {
        var tax_base_amount = base;
      } else {
        tax_base_amount = total_excluded;
      }

      if (tax.price_include && cached_tax_amounts.hasOwnProperty(i)) {
        var tax_amount = cached_tax_amounts[i];
      } else if (!skip_checkpoint && tax.price_include && total_included_checkpoints[i] !== undefined) {
        var tax_amount = total_included_checkpoints[i] - (base + cumulated_tax_included_amount);
        cumulated_tax_included_amount = 0;
      } else {
        var tax_amount = self._compute_all(tax, tax_base_amount, quantity, true);
      }

      tax_amount = round_pr(tax_amount, currency_rounding);
      var factorized_tax_amount = round_pr(
        tax_amount * tax.sum_repartition_factor,
        currency_rounding
      );

      if (tax.price_include && total_included_checkpoints[i] === undefined) {
        cumulated_tax_included_amount += factorized_tax_amount;
      }

      taxes_vals.push({
        id: tax.id,
        name: tax.name,
        amount: sign * factorized_tax_amount,
        base: sign * round_pr(tax_base_amount, currency_rounding),
      });

      if (tax.include_base_amount) {
        base += factorized_tax_amount;
        if (!tax.price_include) {
          skip_checkpoint = true;
        }
      }

      total_included += factorized_tax_amount;
      i += 1;
    });

    return {
      taxes: taxes_vals,
      total_excluded: sign * round_pr(total_excluded, initial_currency_rounding),
      total_included: sign * round_pr(total_included, initial_currency_rounding),
    };
  },

  format_foreign_currency(amount, precision) {

    amount = this.format_currency_no_symbol(
      amount,
      precision,
      this.foreign_currency
    );
    if (this.foreign_currency.position === 'after') {
      return amount + ' ' + (this.foreign_currency.symbol || '');
    } else {
      return (this.foreign_currency.symbol || '') + ' ' + amount;
    }
  }
})
