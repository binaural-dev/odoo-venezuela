/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { useEnv } from "@odoo/owl";

// New orders are now associated with the current table, if any.
patch(PaymentScreen.prototype, {

  setup(){
    super.setup(...arguments)
    this.utils = useEnv().utils,
     this.dialog = useService("dialog");
  },
  get foreignTotalDueText() {
    // Delegates to pos.order.get_foreign_total_with_tax (single source of
    // truth for foreign totals; see rounding-rule engram memory).
    const order = this.currentOrder;
    const amount = order && typeof order.get_foreign_total_with_tax === "function"
      ? Number(order.get_foreign_total_with_tax()) || 0
      : 0;
    return this.env.utils.formatForeignCurrency(amount);
  },
  async addNewPaymentLine(method) {
    // Snapshot the local due BEFORE super attaches the new payment line
    // (after attachment remainingDue drops to zero).
    // Odoo 19: remainingDue getter replaces get_due().
    const order = this.currentOrder;
    const localDueBefore = Number(
      order?.remainingDue ??
      (typeof order?.get_due === "function" ? order.get_due() : 0)
    ) || 0;
    const result = await super.addNewPaymentLine(method);

    if (method?.is_foreign_currency && localDueBefore > 0) {
      const line = this.selectedPaymentLine;
      const order = this.currentOrder;
      if (line && order && typeof line.set_foreign_amount === "function" &&
          typeof order.localToForeign === "function") {
        // Use raw (unrounded) conversion, then FLOOR to the foreign
        // currency's precision so the paid foreign amount never exceeds the
        // local due (avoids off-by-one-cent overpayment).
        const foreignDue = order.localToForeign(localDueBefore, false);
        const dp = Number(order?.get_foreign_currency?.()?.decimal_places) || 2;
        const factor = Math.pow(10, dp);
        const floored = Math.floor(foreignDue * factor) / factor;
        line.set_foreign_amount(floored);
        this.numberBuffer.set(floored.toFixed(dp));
      }
    }
    return result;
  },
  shouldDownloadInvoice() {
    return false;
  },
  updateSelectedPaymentline(amount = false) {
    if (this.paymentLines.every((line) => line.paid)) {
      this.currentOrder.addPaymentline(this.payment_methods_from_config[0]);
    }
    if (!this.selectedPaymentLine) {
      return;
    } // do nothing if no selected payment line

    const selectedMethod = this.selectedPaymentLine.payment_method_id;
    if (!selectedMethod) {
      return super.updateSelectedPaymentline(amount);
    }

    // >>  BINAURAL
    if (!selectedMethod.is_foreign_currency) {
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

    // disable changing amount on paymentlines with running or done payments on a payment terminal
    const payment_terminal = selectedMethod.payment_terminal;
    const hasCashPaymentMethod = this.payment_methods_from_config.some(
      (method) => method.type === "cash"
    );
    // Odoo 19: remainingDue getter replaces get_due().
    const currentDue = Number(
      this.currentOrder?.remainingDue ??
      (typeof this.currentOrder?.get_due === "function" ? this.currentOrder.get_due() : 0)
    ) || 0;
    if (
      !hasCashPaymentMethod &&
      amount > currentDue + this.selectedPaymentLine.amount
    ) {
      this.selectedPaymentLine.setAmount(0);
      this.numberBuffer.set(currentDue.toString());
      amount = currentDue;
      this.showMaxValueError();
    }
    if (
      payment_terminal &&
      !["pending", "retry"].includes(this.selectedPaymentLine.getPaymentStatus())
    ) {
      return;
    }
    if (amount === null) {
      this.deletePaymentLine(this.selectedPaymentLine.uuid);
    } else {
      if (selectedMethod.is_foreign_currency && typeof this.selectedPaymentLine.set_foreign_amount === "function") {
        this.selectedPaymentLine.set_foreign_amount(amount);
      } else {
        this.selectedPaymentLine.setAmount(amount);
      }
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
    let id = []
    if (Object.values(this.pos.toRefundLines).length == 0) {
      return
    }
    Object.values(this.pos.toRefundLines).forEach(el => {
      id = el.orderline.orderBackendId
    })

    const payments = await this.orm.call('pos.order', 'get_payments_order_refund', [id]);

    let payment_list = payments.map(el => {
      return {
        id: el.id,
        label: el.payment_method_id[1] + " " + el.display_name + " / " + this.utils.formatForeignCurrency(el.foreign_amount),
        isSelected: false,
        item: el,
      }

    })
    await this.popup.add(
      SelectionPopup,
      {
        title: _t("Payments"),
        list: payment_list,
      }
    )
  }
})
