/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";

// New orders are now associated with the current table, if any.
patch(PaymentScreen.prototype, {

  _isRefundOrder(order = this._getCurrentOrder()) {
    return Boolean(order?.is_refund || order?.isRefund);
  },

  _recomputeOrderPaymentState(order = this._getCurrentOrder()) {
    order?.update_igtf();
    if (this._isRefundOrder(order)) {
      this._syncRefundAutoPaymentLine(order);
    }
  },

  async setup() {
    super.setup(...arguments);
    this.orm = useService("orm");
    this.state = useState({
      total_paid_amount: 0,
    });

    const originalOrder = this.pos.selectedOrderData;
    if (this.currentOrder?.is_refund && originalOrder?.id) {
      try {
        await this.get_order_from_back(originalOrder.id);
      } catch (error) {
        console.error("Failed to load original order data for refund:", error);
      }
    }

    this._getCurrentOrder()?.update_igtf();
  },

    _syncRefundAutoPaymentLine(order = this._getCurrentOrder()) {
     if (!order?.is_refund) {
       return;
     }

     const paymentLinesSource =
       (typeof order._get_order_payment_lines === "function" && order._get_order_payment_lines()) ||
       order?.payment_ids ||
       [];
     const paymentLines = Array.isArray(paymentLinesSource)
       ? paymentLinesSource
       : Array.from(paymentLinesSource || []);

     if (!Array.isArray(paymentLines) || !paymentLines.length) {
       return;
     }

     const editableLines = paymentLines.filter(
       (line) => !line?.is_change && !(typeof line?.isChange === "function" && line.isChange()),
     );
     if (editableLines.length !== 1) {
       return;
     }

     // Calculate pending amount using Odoo base logic: totalDue - amountPaid
     const pendingDue = 
       order.totalDue - order.amountPaid

     const paymentLine = editableLines[0];
     const currentAmount = Number(paymentLine.amount) || 0;
     const targetAmount = currentAmount + pendingDue;

     paymentLine.amount = targetAmount;
   },

  async addNewPaymentLine(paymentMethod) {
    const res = await super.addNewPaymentLine(...arguments);
    const order = this._getCurrentOrder();
    if (res) {
      this._recomputeOrderPaymentState(order);
    }

    this.render();
    return res;
  },

  updateSelectedPaymentline(amount = false) {
    super.updateSelectedPaymentline(amount);
    const order = this._getCurrentOrder();
    this._recomputeOrderPaymentState(order);
    this.render();
  },

  deletePaymentLine() {
    super.deletePaymentLine(...arguments);
    const order = this._getCurrentOrder();
    this._recomputeOrderPaymentState(order);
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

    const order = this._getCurrentOrder();
    order?.set_total_from_backend(orderData);
    this._recomputeOrderPaymentState(order);

    if (this.__owl__?.isMounted) {
        this.render();
    }
  },

  async validateOrder() {
    return super.validateOrder(...arguments);
  }
})
