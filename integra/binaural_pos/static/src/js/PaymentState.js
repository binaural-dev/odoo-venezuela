odoo.define("binaural_pos.PaymentState", function(require) {
  "use strict";

  const { Payment } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");
  const utils = require("web.utils");

  var round_pr = utils.round_precision;
  var round_di = utils.round_decimals;

  const BinauralPayment = (Payment) =>
    class BinauralPayment extends Payment {
      constructor() {
        super(...arguments);
        this.foreign_amount = 0;
      }
      export_as_JSON() {
        let res = super.export_as_JSON();
        res["foreign_amount"] = this.get_foreign_amount();
        return res
      }
      get_foreign_amount() {
        return round_pr(
          this.amount * this.pos.config.foreign_inverse_rate,
          this.pos.foreign_currency.rounding
        );
      }
      set_foreign_amount(value) {
        this.foreign_amount = value
        this.amount = round_di(parseFloat(value) || 0, this.pos.foreign_currency.decimal_places);
      }
    }
  Registries.Model.extend(Payment, BinauralPayment);
  return BinauralPayment;
})
