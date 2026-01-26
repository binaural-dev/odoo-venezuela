/** @odoo-module **/

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

patch(Order.prototype, {
  init_from_JSON(json) {
    super.init_from_JSON(json);
    this.fiscal_machine = json.fiscal_machine || false;
    this.mf_invoice_number = json.mf_invoice_number || false;
    this.mf_reportz = this.mf_reportz || false;
  },
  export_as_JSON() {
    let res = super.export_as_JSON();
    res.fiscal_machine = this.fiscal_machine;
    res.mf_invoice_number = this.mf_invoice_number;
    res.mf_reportz = this.mf_reportz;
    return res;
  },
  assert_editable() {
    return
  }
})
