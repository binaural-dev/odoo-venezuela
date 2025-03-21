odoo.define("l10n_ve_pos_igtf.PaymentState", function(require) {
  "use strict";

  const { Payment } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");


  const BinauralPaymentState = (Payment) =>
    class BinauralPaymentState extends Payment {
      constructor() {
        super(...arguments)
        this.include_igtf = this.include_igtf || false
        this.igtf_amount = this.igtf_amount || 0
        this.foreign_igtf_amount = this.foreign_igtf_amount || 0
      }
      set_include_igtf(value) {
        this.include_igtf = value
      }
      set_igtf_amount(amount){
        this.igtf_amount = amount
      }
      set_foreign_igtf_amount(amount){
        this.foreign_igtf_amount = amount
      }
      init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.include_igtf = json.include_igtf || false;
        this.igtf_amount = json.igtf_amount || 0;
        this.foreign_igtf_amount = json.foreign_igtf_amount || 0;
      }
      export_as_JSON() {
        let res = super.export_as_JSON();
        res["include_igtf"] = this.include_igtf;
        res["igtf_amount"] = this.igtf_amount;
        res["foreign_igtf_amount"] = this.foreign_igtf_amount;
        return res
      }
    };
  Registries.Model.extend(Payment, BinauralPaymentState);
  return BinauralPaymentState;
})
