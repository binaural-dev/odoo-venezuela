/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";

// New orders are now associated with the current table, if any.
patch(PaymentScreen.prototype, {

  _getRefundLineOriginalLineIds(order = this._getCurrentOrder()) {
    const linesSource =
      (typeof order?.get_orderlines === "function" && order.get_orderlines()) ||
      order?.orderlines ||
      order?.lines ||
      [];
    const lines = Array.isArray(linesSource) ? linesSource : Array.from(linesSource || []);

    const ids = [];
    for (const line of lines) {
      const candidate = line?.refunded_orderline_id || line?.refundedOrderlineId || null;
      if (!candidate) {
        continue;
      }
      const idRaw = Array.isArray(candidate)
        ? candidate[0]
        : typeof candidate === "object"
          ? candidate?.id
          : candidate;
      const id = Number(idRaw);
      if (Number.isFinite(id) && id > 0) {
        ids.push(id);
      }
    }
    return [...new Set(ids)];
  },

  async _resolveRefundedOrderIdFromLines(order = this._getCurrentOrder()) {
    const originalLineIds = this._getRefundLineOriginalLineIds(order);
    if (!originalLineIds.length) {
      return null;
    }

    try {
      const rows = await this.orm.call(
        "pos.order.line",
        "search_read",
        [["id", "in", originalLineIds]],
        {
          fields: ["id", "order_id"],
          limit: 1,
        },
      );
      const orderField = rows?.[0]?.order_id;
      const orderIdRaw = Array.isArray(orderField) ? orderField[0] : orderField;
      const orderId = Number(orderIdRaw);
      return Number.isFinite(orderId) && orderId > 0 ? orderId : null;
    } catch (error) {
      console.warn("Failed to resolve refunded order id from lines", error);
      return null;
    }
  },

  _getRefundedOrderId(order = this._getCurrentOrder()) {
    if (!order) {
      return null;
    }
    const candidate =
      order?.refunded_order_id?.id ||
      order?.refunded_order_id ||
      order?.refund_order_id?.id ||
      order?.refund_order_id ||
      order?.refundedOrderId ||
      this.pos?.selectedOrderData?.id;
    const id = Number(candidate);
    return Number.isFinite(id) && id > 0 ? id : null;
  },

  async _ensureRefundBackendTotalsLoaded(order = this._getCurrentOrder()) {
    if (!this._isRefundOrder(order) || order?._refundTotalsLoaded) {
      return;
    }
    let refundedOrderId = this._getRefundedOrderId(order);
    if (!refundedOrderId) {
      refundedOrderId = await this._resolveRefundedOrderIdFromLines(order);
    }
    if (!refundedOrderId) {
      console.warn("Refund order has no original order id yet", {
        is_refund: order?.is_refund,
        isRefund: order?.isRefund,
      });
      return;
    }
    await this.get_order_from_back(refundedOrderId);
  },

  _isRefundOrder(order = this._getCurrentOrder()) {
    return Boolean(order?.is_refund || order?.isRefund);
  },

  _recomputeOrderPaymentState(order = this._getCurrentOrder()) {
    order?.update_igtf();
    if (this._isRefundOrder(order)) {
      this._syncRefundAutoPaymentLine(order);
    }
    order?._debug_financial_snapshot?.("payment_screen:_recomputeOrderPaymentState");
  },

  async setup() {
    super.setup(...arguments);
    this.orm = useService("orm");
    this.state = useState({
      total_paid_amount: 0,
    });

    const order = this._getCurrentOrder();
    if (this._isRefundOrder(order)) {
      try {
        await this._ensureRefundBackendTotalsLoaded(order);
      } catch (error) {
        console.error("Failed to load original order data for refund:", error);
      }
    }

    this._getCurrentOrder()?.update_igtf();
  },

    _syncRefundAutoPaymentLine(order = this._getCurrentOrder()) {
     if (!this._isRefundOrder(order)) {
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

      const paymentLine = editableLines[0];
       if (typeof order?._syncPaymentLineToPendingDue === "function") {
        order._syncPaymentLineToPendingDue(paymentLine);
      } else {
        const currentAmount = Number(paymentLine.amount) || 0;
        const targetAmount = currentAmount + (order.totalDue - order.amountPaid);
        paymentLine.amount = targetAmount;
      }

      order?._syncRefundIgtfPaymentLines?.();
    },

  async addNewPaymentLine(paymentMethod) {
    const order = this._getCurrentOrder();
    await this._ensureRefundBackendTotalsLoaded(order);
    const res = await super.addNewPaymentLine(...arguments);
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
    const totalDue = Number(
      typeof order?.totalDue === "function" ? order.totalDue() : order?.totalDue,
    ) || 0;
    return this.env.utils.formatCurrency(totalDue);
  },

  get suggestedIgtf() {
    const order = this._getCurrentOrder();
    return this.env.utils.formatCurrency(order?.get_igtf_amount?.() || 0);
  },

  get totalDueTextWithIGTFDisplay() {
    const order = this._getCurrentOrder();
    const totalDue = Number(
      typeof order?.totalDue === "function" ? order.totalDue() : order?.totalDue,
    ) || 0;
    return this.env.utils.formatCurrency(totalDue);
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
    order?.set_totals_from_backend(orderData);
    if (order) {
      order._refundTotalsLoaded = true;
    }
    
    order?.set_mf_info_from_backend(orderData);

    this._recomputeOrderPaymentState(order);

    if (this.__owl__?.isMounted) {
        this.render();
    }
  },

  async validateOrder() {
    const order = this._getCurrentOrder();
    await this._ensureRefundBackendTotalsLoaded(order);
    order?._debug_financial_snapshot?.("payment_screen:validateOrder:before");
    return super.validateOrder(...arguments);
  }
})
