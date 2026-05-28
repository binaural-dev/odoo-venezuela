/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";

// New orders are now associated with the current table, if any.
patch(PaymentScreen.prototype, {

  async setup() {
    super.setup(...arguments);
    this.orm = useService("orm");
    this._getCurrentOrder()?.update_igtf();
    this.state = useState({
      total_paid_amount: 0,
    })
    const originalOrder = this.pos.selectedOrderData;
    if (this.currentOrder?.is_refund && originalOrder) {
      await this.get_order_from_back(originalOrder.id);
    }
  },

  async addNewPaymentLine(paymentMethod) {
    const res = await super.addNewPaymentLine(...arguments);
    const order = this._getCurrentOrder();

    order?.update_igtf();

    this.render();
    return res;
  },

  updateSelectedPaymentline(amount = false) {
    super.updateSelectedPaymentline(amount);
    const order = this._getCurrentOrder();
    order?.update_igtf();
    this.render();
  },

  deletePaymentLine() {
    super.deletePaymentLine(...arguments);
    const order = this._getCurrentOrder();
    order?.update_igtf();
    this.render();
  },

  toggleIsToInvoice() {
    super.toggleIsToInvoice();
    const order = this._getCurrentOrder();
    order?.update_igtf();
    this.render();
  },

  _getCurrentOrder() {
    return this.currentOrder || this.pos.get_order();
  },

  get totalDueText() {
    const order = this._getCurrentOrder();
    return this.env.utils.formatCurrency(order?.get_total_without_igtf?.() || 0);
  },

  get suggestedIgtf() {
    const order = this._getCurrentOrder();
    const percentage = order?._get_order_igtf_percentage?.() || this.config.igtf_percentage || 0;
    const base = order?.get_total_with_tax?.() || 0;
    const result = base * (percentage / 100)
    return this.env.utils.formatCurrency(result);
  },

  get totalDueTextWithIGTFDisplay() {
    const order = this._getCurrentOrder();

    const percentage = order?._get_order_igtf_percentage?.() || this.config.igtf_percentage || 0;

    const base = order?.get_total_with_tax?.() || 0;
    return this.env.utils.formatCurrency(base + (base * (percentage / 100)));
  },

  get biAmount() {
    const order = this._getCurrentOrder();
    return this.env.utils.formatCurrency(order?.get_bi_igtf?.() || 0, "Product Price");
  },

  get igtfAmount() {
    const order = this._getCurrentOrder();
    return this.env.utils.formatCurrency(order?.get_igtf_amount?.() || 0, "Product Price");
  },

  get igtfForeignAmount() {
    const order = this._getCurrentOrder();
    return this.env.utils.formatForeignCurrency(order?.get_foreign_igtf_amount?.() || 0, "Product Price");
  },

  async get_order_from_back(id) {
    const orderData = await this.orm.call("pos.order", "get_order_from_back", [id],
        { context: { id } });
    this._getCurrentOrder()?.set_total_from_backend(orderData)
    this.render()
  }
})
