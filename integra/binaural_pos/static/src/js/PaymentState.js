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
        this.foreign_rate = this.pos.config.foreign_rate;
      }
      export_as_JSON() {
        let res = super.export_as_JSON();
        res["foreign_amount"] = this.get_foreign_amount();
        res["foreign_rate"] = this.foreign_rate;
        return res
      }
      get_foreign_amount() {
        return this.foreign_amount;
      }
      set_foreign_amount(value) {
        this.foreign_amount = value
      }
    }
  Registries.Model.extend(Payment, BinauralPayment);
  return BinauralPayment;
})
