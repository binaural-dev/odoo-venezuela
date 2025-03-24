/** @odoo-module */

import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { useEnv } from "@odoo/owl";

// New orders are now associated with the current table, if any.
patch(PaymentScreen.prototype, {

  setup(){
    super.setup(...arguments)
    this.utils = useEnv().utils
  },
  shouldDownloadInvoice() {
    return false;
  },
  updateSelectedPaymentline(amount = false) {
    if (this.paymentLines.every((line) => line.paid)) {
      this.currentOrder.add_paymentline(this.payment_methods_from_config[0]);
    }
    if (!this.selectedPaymentLine) {
      return;
    } // do nothing if no selected payment line

    // >>  BINAURAL
    if (!this.selectedPaymentLine.payment_method.is_foreign_currency) {
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
    const payment_terminal = this.selectedPaymentLine.payment_method.payment_terminal;
    const hasCashPaymentMethod = this.payment_methods_from_config.some(
      (method) => method.type === "cash"
    );
    if (
      !hasCashPaymentMethod &&
      amount > this.currentOrder.get_due() + this.selectedPaymentLine.amount
    ) {
      this.selectedPaymentLine.set_amount(0);
      this.numberBuffer.set(this.currentOrder.get_due().toString());
      amount = this.currentOrder.get_due();
      this.showMaxValueError();
    }
    if (
      payment_terminal &&
      !["pending", "retry"].includes(this.selectedPaymentLine.get_payment_status())
    ) {
      return;
    }
    if (amount === null) {
      this.deletePaymentLine(this.selectedPaymentLine.cid);
    } else {
      if (this.selectedPaymentLine.payment_method.is_foreign_currency) {
        this.selectedPaymentLine.set_foreign_amount(amount);
      } else {
        this.selectedPaymentLine.set_amount(amount);
      }
    }
  },
  toggleIsToInvoice() {
    this.currentOrder.toggle_receipt_invoice(!this.currentOrder.is_to_receipt());
  },
  async _isOrderValid(isForceValidate) {
    let res = await super._isOrderValid(isForceValidate)
    if (!this.currentOrder) {
      return res
    }

    let amounts = this.currentOrder.get_paymentlines().map((el) => el.amount)
    if (!amounts.every((el) => el != 0 && this.currentOrder.get_total_with_tax() !== 0)) {
      this.popup.add(ErrorPopup, {
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
