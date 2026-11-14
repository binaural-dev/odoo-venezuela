/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { onWillStart } from "@odoo/owl";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";
import { GT } from "@point_of_sale/app/utils/numbers";

// New orders are now associated with the current table, if any.
patch(PaymentScreen.prototype, {

  setup(){
    super.setup(...arguments)
    this.dialog = useService("dialog");
    this.orm = useService("orm");
    // For a refund, prefetch (before the screen renders) the exact rate the
    // original order's foreign tender used, so foreign refund payment lines
    // mirror the original payment to the cent (see pos_order.getRefundForeignRate).
    onWillStart(async () => {
      await this._prefetchRefundForeignRate();
    });
  },
  async _prefetchRefundForeignRate() {
    const order = this.currentOrder;
    if (!order || !order.isRefund) {
      return;
    }
    const originOrderIds = new Set();
    for (const line of order.lines || []) {
      const id = line.refunded_orderline_id?.order_id?.id;
      if (id) {
        originOrderIds.add(id);
      }
    }
    if (!originOrderIds.size) {
      return;
    }
    try {
      const rate = await this.orm.call("pos.order", "get_refund_foreign_rate", [
        Array.from(originOrderIds),
      ]);
      const numericRate = Number(rate);
      if (Number.isFinite(numericRate) && numericRate > 0) {
        // Cached on the order; the sync conversion helpers read it.
        order.refund_foreign_rate = numericRate;
      }
    } catch (error) {
      // Non-fatal: fall back to the aggregate-rate conversion.
      console.warn("[l10n_ve_pos] no se pudo prefetch la tasa de reembolso:", error);
    }
  },
  get foreignTotalDueText() {
    // Delegates to pos.order.get_foreign_total_with_tax (single source of
    // truth for foreign totals; see rounding-rule engram memory).
    const order = this.currentOrder;
    const amount = order && typeof order.get_foreign_total_with_tax === "function"
      ? Number(order.get_foreign_total_with_tax()) || 0
      : 0;
    return this.pos.formatForeignCurrency(amount);
  },
  async addNewPaymentLine(paymentMethod, args = {}) {
    // Same as the core method but without its "only one currency by order"
    // refusal: a sale can be paid in Bs, USD and EUR at once (the server groups
    // the payments by method and currency). Keep in sync with
    // point_of_sale PaymentScreen.addNewPaymentLine.
    const { status: canSend, message } = paymentMethod.getPaymentInterfaceStates();
    if (!canSend) {
      this.dialog.add(AlertDialog, { title: _t("Oh snap !"), body: message });
      return;
    }
    if (this.paymentLines.length === 0) {
      this.makeAnimation();
    }
    const order = this.currentOrder;
    const localDueBefore = Number(order?.remainingDue) || 0;
    const result = order.addPaymentline(paymentMethod, args);
    if (!result.status) {
      this.dialog.add(AlertDialog, {
        title: _t("Oh snap !"),
        body: result.data,
        size: result.size,
      });
      return false;
    }
    const line = result.data;
    if (line.isForeignPayment && localDueBefore !== 0) {
      // The remaining due in the currency the customer pays with, converted
      // once from the LOCAL due; a refund uses the frozen original rate. The
      // "covers the due" branch of set_foreign_amount absorbs the fx noise.
      const foreignDue = line._localToPaymentCurrency(localDueBefore);
      line.setAmount(foreignDue, line.currency);
      // Locale-aware formatting: a toFixed() "3.88" would be read as 388 in
      // es_VE, where "." is the thousands separator.
      this.numberBuffer.set(
        this.pos.formatCurrency(foreignDue, line.currency.id, { noSymbol: true })
      );
    } else if (localDueBefore !== 0) {
      this.numberBuffer.set(
        this.pos.formatCurrency(line.getAmount(), undefined, { noSymbol: true })
      );
    } else {
      this.numberBuffer.set(line.amount.toString());
    }
    if (!this.isRefundOrder && paymentMethod.useBankQrCode) {
      this.sendPaymentRequest(this.paymentLines.at(-1));
    }
    return true;
  },
  shouldDownloadInvoice() {
    return false;
  },
  updateSelectedPaymentline(amount = false) {
    const line = this.selectedPaymentLine;
    if (!line?.isForeignPayment) {
      return super.updateSelectedPaymentline(amount);
    }

    if (amount === false) {
      if (this.numberBuffer.get() === null) {
        amount = null;
      } else if (this.numberBuffer.get() === "") {
        amount = 0;
      } else {
        amount = this.numberBuffer.getFloat();
      }
    }

    const hasCashPaymentMethod = this.payment_methods_from_config.some(
      (method) => method.type === "cash"
    );
    const currentDue = Number(this.currentOrder?.remainingDue) || 0;
    const cur = this.pos.currency;
    const limit = currentDue + line.amount;
    const absAmount = amount < 0 ? -amount : amount;
    const absLimit = limit < 0 ? -limit : limit;
    if (!hasCashPaymentMethod && cur.comp(absAmount, absLimit) === GT) {
      const maxAmount = currentDue < 0 ? -currentDue : currentDue;
      line.setAmount(0);
      this.numberBuffer.set(maxAmount.toString());
      amount = maxAmount;
      this.showMaxValueError();
    }
    if (
      line.payment_interface &&
      !["pending", "retry"].includes(line.getPaymentStatus())
    ) {
      return;
    }
    if (amount === null) {
      this.deletePaymentLine(line.uuid);
    } else {
      line.setAmount(amount, line.currency);
    }
  },
  async _isOrderValid(isForceValidate) {
    let res = await super._isOrderValid(isForceValidate)
    if (!this.currentOrder) {
      return res
    }

    // Odoo 19: get_paymentlines() → payment_ids; get_total_with_tax() → totalDue.
    const paymentLines = typeof this.currentOrder.get_paymentlines === "function"
      ? this.currentOrder.get_paymentlines()
      : Array.from(this.currentOrder.payment_ids || []);
    const orderTotal = Number(
      this.currentOrder.totalDue ??
      (typeof this.currentOrder.get_total_with_tax === "function" ? this.currentOrder.get_total_with_tax() : 0)
    ) || 0;
    let amounts = paymentLines.map((el) => el.amount)
    if (!amounts.every((el) => el != 0 && orderTotal !== 0)) {
      this.dialog.add(AlertDialog, {
        title: _t('Empty Paymentline'),
        body: _t(
          "You can't validate with empty payment lines"),
      })
      return false
    }
    return res
  },
  async showPaymentsOrigin() {
    // En Odoo 19, obtener las órdenes origen desde las líneas de reembolso
    const order = this.currentOrder;
    if (!order || !order.isRefund) {
      return;
    }

    // Recopilar IDs únicos de órdenes origen
    const originOrderIds = new Set();
    for (const line of order.lines) {
      if (line.refunded_orderline_id?.order_id?.id) {
        originOrderIds.add(line.refunded_orderline_id.order_id.id);
      }
    }

    if (originOrderIds.size === 0) {
      console.warn("No se encontraron órdenes origen para este reembolso");
      return;
    }

    try {
      // Obtener pagos de las órdenes origen
      const payments = await this.orm.call("pos.order", "get_payments_order_refund", [
        Array.from(originOrderIds),
      ]);

      if (!payments || payments.length === 0) {
        this.dialog.add(AlertDialog, {
          title: _t("Sin pagos"),
          body: _t("No se encontraron pagos en la orden original"),
        });
        return;
      }

      const payment_list = payments.map(el => {
        return {
          id: el.id,
          label: `${el.payment_method_id?.[1] || _t("Método desconocido")} ${el.display_name || ""} / ${this.pos.formatForeignCurrency(el.foreign_amount || el.amount || 0)}`,
          isSelected: false,
          item: el,
        }
      });

      await makeAwaitable(this.dialog, SelectionPopup, {
        title: _t("Pagos de la orden original"),
        list: payment_list,
      });
    } catch (error) {
      console.error("Error obteniendo pagos origen:", error);
      this.dialog.add(AlertDialog, {
        title: _t("Error"),
        body: _t("No se pudieron obtener los pagos de la orden original"),
      });
    }
  }
})
