/** @odoo-module */
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";
import { SelectionPopup } from "@point_of_sale/app/components/popups/selection_popup/selection_popup";
import { useEnv } from "@odoo/owl";

patch(PaymentScreen.prototype, {

  setup() {

    super.setup(...arguments)
    this.utils = useEnv().utils,
    this.dialog = useService("dialog");

  },

  get foreignTotalDueTexts() {
    return this.utils.formatForeignCurrency(this.currentOrder.get_foreign_total_with_taxes())
  },

  // shouldDownloadInvoice() {
  //   return true;
  // },

  add_paymentline(payment_method) {
    let is_change = false;
    let is_return = this.get_total_without_igtf() < 0;
    if (!is_return) {
      is_change = this.get_due() < 0;
    } else {
      is_change = this.get_due() > 0;
    }

    if (
      !payment_method.apply_igtf ||
      this.get_due() <= this.get_igtf_amount() ||
      is_change
    ) {
      let res = super.add_paymentline(...arguments);
      this.update_igtf();
      return res;
    }
    let res_igtf = this.add_paymentline_without_igtf(...arguments);
    this.update_igtf();
    return res_igtf;
  },
  
  updateSelectedPaymentline(amount) {
    return super.updateSelectedPaymentline(amount);
  },
  
  async validateOrder(isForceValidate) {
    const order = this.currentOrder || this.pos.get_order();
    const selectedLine =
      order?.getSelectedPaymentline?.() ||
      order?.selected_paymentline ||
      null;

    return await super.validateOrder(isForceValidate);
  },

  toggleIsToInvoice() {
    this.currentOrder.toggle_receipt_invoice(!this.currentOrder.is_to_receipt());
    this.render();
  },


  async _isOrderValid(isForceValidate) {
    let res = await super._isOrderValid(isForceValidate)
    if (!this.currentOrder) {
      return res
    }

    this.currentOrder?._debug_financial_snapshot?.("l10n_ve_pos:_isOrderValid:afterSuper");
    if (!res) {
      const order = this.currentOrder;
      const totalDue = Number(
        typeof order.totalDue === "function" ? order.totalDue() : order.totalDue,
      ) || 0;
      const amountPaid = Number(
        typeof order.amountPaid === "function" ? order.amountPaid() : order.amountPaid,
      ) || 0;
      const remainingDue = Number(order.remainingDue) || 0;
      console.log("[IGTF][DEBUG] l10n_ve_pos:_isOrderValid:failed", {
        uid: order.uid,
        isPaid: typeof order.isPaid === "function" ? Boolean(order.isPaid()) : null,
        totalDue,
        amountPaid,
        remainingDue,
        dueGetter: typeof order.get_due === "function" ? Number(order.get_due()) || 0 : null,
        foreignDue: typeof order.get_foreign_due === "function" ? Number(order.get_foreign_due()) || 0 : null,
        pendingFromTotal: totalDue - amountPaid,
        paymentlines: (order.get_paymentlines?.() || order.paymentlines || order.payment_ids || []).map((line) => ({
          amount: Number(line?.amount) || 0,
          foreign_amount: Number(line?.foreign_amount) || 0,
          is_done: typeof line?.is_done === "function" ? line.is_done() : null,
          payment_status: line?.payment_status || null,
          apply_igtf: Boolean(line?.payment_method?.apply_igtf),
          method: line?.payment_method?.name || null,
        })),
      });
    }

    let amounts = this.currentOrder.get_paymentlines().map((el) => el.amount)
    let hasEmptyPayment = amounts.some((el) => el == 0);
    if (hasEmptyPayment && this.currentOrder.get_total_with_tax() !== 0) {
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
    const originalOrder = this.currentOrder.refunded_order_id;
    if (!originalOrder) return;

    const ids = [originalOrder.id];
    const payments = await this.orm.call('pos.order', 'get_payments_order_refund', [ids]);

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
