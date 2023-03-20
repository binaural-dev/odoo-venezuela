odoo.define("binaural_pos.PaymentState", function(require) {
  "use strict";

  const { Payment } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");
  const utils = require("web.utils");

  var round_pr = utils.round_precision;

  const BinauralPayment = (Payment) =>
    class BinauralPayment extends Payment {
      get_foreign_amount() {
        return round_pr(
          this.amount * this.pos.config.foreign_inverse_rate,
          this.pos.foreign_currency.rounding
        );
      }
    }
  Registries.Model.extend(Payment, BinauralPayment);
  return BinauralPayment;
})
