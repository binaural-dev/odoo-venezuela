odoo.define("binaural_pos.OrderState", function(require) {
  "use strict";

  const { Order } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");
  const utils = require("web.utils");

  var round_pr = utils.round_precision;

  const BinauralOrderState = (Order) =>
    class BinauralOrderState extends Order {
      constructor(){
        super(...arguments);
        this.to_invoice = true;
      }
      get_foreign_total_tax() {
        if (this.pos.company.tax_calculation_rounding_method === "round_globally") {
          // As always, we need:
          // 1. For each tax, sum their amount across all order lines
          // 2. Round that result
          // 3. Sum all those rounded amounts
          var groupTaxes = {};
          this.orderlines.forEach(function(line) {
            var taxDetails = line.get_foreign_tax_details();
            var taxIds = Object.keys(taxDetails);
            for (var t = 0; t < taxIds.length; t++) {
              var taxId = taxIds[t];
              if (!(taxId in groupTaxes)) {
                groupTaxes[taxId] = 0;
              }
              groupTaxes[taxId] += taxDetails[taxId];
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
          return round_pr(this.orderlines.reduce((function(sum, orderLine) {
            return sum + orderLine.get_foreign_tax();
          }), 0), this.pos.foreign_currency.rounding);
        }
      }
      get_foreign_total_without_tax() {
        return round_pr(this.orderlines.reduce((function(sum, orderLine) {
          return sum + orderLine.get_foreign_price_without_tax();
        }), 0), this.pos.foreign_currency.rounding);
      }
      get_foreign_total_with_tax() {
        return this.get_foreign_total_without_tax() + this.get_foreign_total_tax();
      }

    };
  Registries.Model.extend(Order, BinauralOrderState);
  return BinauralOrderState;
})
