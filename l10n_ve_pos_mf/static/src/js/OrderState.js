/** @odoo-module **/

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";
import { getFiscalTripletFromJSON } from "./fiscal_payload_utils";

patch(Order.prototype, {
  init_from_JSON(json) {
    super.init_from_JSON(json);
    const fiscalTriplet = getFiscalTripletFromJSON(json);
    this.fiscal_machine = fiscalTriplet.fiscal_machine;
    this.mf_invoice_number = fiscalTriplet.mf_invoice_number;
    this.mf_reportz = fiscalTriplet.mf_reportz;
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
