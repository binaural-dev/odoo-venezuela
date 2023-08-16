odoo.define("binaural_pos_igtf.PaymentState", function(require) {
  "use strict";

  const { Payment } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");


  const BinauralPaymentState = (Payment) =>
    class BinauralPaymentState extends Payment {
      constructor() {
        super(...arguments)
        this.include_igtf = this.include_igtf || false
      }
      set_include_igtf(value) {
        this.include_igtf = value
      }
      init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.include_igtf = json.include_igtf || false;
      }
      export_as_JSON() {
        let res = super.export_as_JSON();
        res["include_igtf"] = this.include_igtf;
        return res
      }
    };
  Registries.Model.extend(Payment, BinauralPaymentState);
  return BinauralPaymentState;
})
