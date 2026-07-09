/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { useEnv } from "@odoo/owl";
import { makeAwaitable } from "@point_of_sale/app/utils/make_awaitable_dialog";

// New orders are now associated with the current table, if any.
patch(PaymentScreen.prototype, {

  setup(){
    super.setup(...arguments)
    this.utils = useEnv().utils;
    this.dialog = useService("dialog");
    this.orm = useService("orm");
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

    if (method?.is_foreign_currency && localDueBefore !== 0) {
      const line = this.selectedPaymentLine;
      const order = this.currentOrder;
      if (line && order && typeof line.set_foreign_amount === "function" &&
          typeof order.localToForeign === "function") {
        // Convert the LOCAL remaining due to foreign using the same
        // rounding as get_foreign_total_with_tax() (foreign_currency.round).
        // No manual floor: the "covers the due" branch in set_foreign_amount
        // handles fx-noise and prevents real overpayment by clamping the
        // local amount to the exact remainingDue. Truncating here would
        // steal a cent whenever the natural round is up.
        const foreignDue = order.localToForeign(localDueBefore);
        line.set_foreign_amount(foreignDue);
        // Use locale-aware formatting (e.g. "-0,01" in es_VE) for the
        // number buffer. NEVER use toFixed() which produces "." decimal
        // separators — Odoo's oParseFloat in es_VE locale treats "." as
        // a thousands separator, turning "3.88" into 388.
        this.numberBuffer.set(
          this.env.utils.formatForeignCurrency(foreignDue, false)
        );
      }
    } else {
      // For LOCAL (non-foreign) methods, the core auto-filled the buffer
      // via result.data.amount.toString() which uses "." as decimal (e.g.
      // "3.88"). Fix: reformat with locale-aware formatting.
      const line = this.selectedPaymentLine;
      if (line && localDueBefore !== 0) {
        const amount = typeof line.getAmount === "function"
          ? line.getAmount()
          : (line.amount || 0);
        this.numberBuffer.set(
          this.env.utils.formatCurrency(amount, false)
        );
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
    // Comparación que funciona con montos negativos (reembolsos):
    // Odoo 19: remainingDue getter replaces get_due().
    const currentDue = Number(
      this.currentOrder?.remainingDue ??
      (typeof this.currentOrder?.get_due === "function" ? this.currentOrder.get_due() : 0)
    ) || 0;
    // Math.abs(amount) > Math.abs(currentDue + selectedPaymentLine.amount)
    if (
      !hasCashPaymentMethod &&
      Math.abs(amount) > Math.abs(currentDue + this.selectedPaymentLine.amount)
    ) {
      this.selectedPaymentLine.setAmount(0);
      this.numberBuffer.set(Math.abs(currentDue).toString());
      amount = Math.abs(currentDue);
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
          label: `${el.payment_method_id?.[1] || _t("Método desconocido")} ${el.display_name || ""} / ${this.utils.formatForeignCurrency(el.foreign_amount || el.amount || 0)}`,
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
