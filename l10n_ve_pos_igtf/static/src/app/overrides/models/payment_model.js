/** @odoo-module */

import { PosPayment } from "@point_of_sale/app/models/pos_payment";
import { patch } from "@web/core/utils/patch";
import {
  formatFloat,
  roundDecimals as round_di,
  roundPrecision as round_pr,
  floatIsZero,
} from "@web/core/utils/numbers";

// New orders are now associated with the current table, if any.
patch(PosPayment.prototype, {
  setup() {
    super.setup(...arguments);
    this.igtf_amount = this.igtf_amount || 0
    this.foreign_igtf_amount = this.foreign_igtf_amount || 0
    this.apply_igtf = this.payment_method_id.apply_igtf || false
    console.log('POS Payment:', this)
  },
  set_include_igtf(value) {
    this.include_igtf = value
  },
  set_igtf_amount(amount) {
    this.igtf_amount = amount
  },
  set_foreign_igtf_amount(amount) {
    this.foreign_igtf_amount = amount
  },
  init_from_JSON(json) {
    super.init_from_JSON(...arguments);
    this.include_igtf = json.include_igtf || false;
    this.igtf_amount = json.igtf_amount || 0;
    this.foreign_igtf_amount = json.foreign_igtf_amount || 0;
    this.apply_igtf = json.apply_igtf || false;
  },
  export_as_JSON() {
    let res = super.export_as_JSON();
    res["include_igtf"] = this.include_igtf;
    res["igtf_amount"] = this.igtf_amount;
    res["foreign_igtf_amount"] = this.foreign_igtf_amount;
    res["apply_igtf"] = this.apply_igtf;
    return res
  },
});
