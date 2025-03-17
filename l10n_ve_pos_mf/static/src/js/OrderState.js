odoo.define("l10n_ve_pos_mf.OrderState", function(require) {
  "use strict";

  const { Order } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");
  const utils = require("web.utils");

  var round_pr = utils.round_precision;

  const BinauralOrderState = (Order) =>
    class BinauralOrderState extends Order {
      constructor(obj, options) {
        super(...arguments);
        this.fiscal_machine = this.fiscal_machine || false;
        this.mf_invoice_number = this.mf_invoice_number || false;
        this.mf_reportz = this.mf_reportz || false;
      }
      init_from_JSON(json) {
        super.init_from_JSON(json);
        this.fiscal_machine = json.fiscal_machine || false;
        this.mf_invoice_number = json.mf_invoice_number || false;
      }
      export_as_JSON() {
        let res = super.export_as_JSON();
        res.fiscal_machine = this.fiscal_machine;
        res.mf_invoice_number = this.mf_invoice_number;
        res.mf_reportz = this.mf_reportz;
        return res;
      }
      assert_editable() {
        return
      }

    };
  Registries.Model.extend(Order, BinauralOrderState);
  return BinauralOrderState;
})
