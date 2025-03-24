/** @odoo-module **/

import { Component } from "@odoo/owl";
import { usePos } from "@point_of_sale/app/store/pos_hook";

export class ReprintInvoiceButton extends Component {
  static template = "binaural_pos_mf.ReprintInvoiceButton";
  setup() {
    super.setup();
    this.pos = usePos()
    // useListener('click', this._onClick);
  }
  async _onClick() {
    if (!this.props.order || this.props.order.mf_invoice_number) return;
    let amount = this.props.order.paymentlines.reduce((prev, cur) => prev + cur.amount, 0)
    const type = amount >= 0 ? "out_invoice" : "out_refund"

    const fdm = this.pos.useFiscalMachine();
    let data = {
      "type": type,
      "mf_number": this.props.order.mf_invoice_number,
    }

    try {
      await fdm.action({
        action: `reprint`,
        data: data,
      }).th
    } catch (err) {}
  }
}
