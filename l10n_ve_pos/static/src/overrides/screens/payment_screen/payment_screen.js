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
  _toNumber(value, fallback = 0) {
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : fallback;
  },
  _getConversionRate() {
    const order = this.currentOrder;
    const candidates = [
      typeof order?.get_conversion_rate === "function" ? order.get_conversion_rate() : undefined,
      order?.init_conversion_rate,
      order?.config?.foreign_inverse_rate,
      order?.pos?.config?.foreign_inverse_rate,
      order?.config?.foreign_rate,
      order?.pos?.config?.foreign_rate,
    ];
    for (const candidate of candidates) {
      const numeric = Number(candidate);
      if (Number.isFinite(numeric) && numeric > 0) {
        return numeric;
      }
    }
    return 0;
  },
  _convertLocalToForeign(amount) {
    const localAmount = this._toNumber(amount, 0);
    const rate = this._getConversionRate();
    if (!rate) {
      return localAmount;
    }
    return rate >= 1 ? localAmount / rate : localAmount * rate;
  },
  get foreignTotalDueText() {
    const fromOrder = typeof this.currentOrder?.get_foreign_total_with_tax === "function"
      ? this._toNumber(this.currentOrder.get_foreign_total_with_tax(), NaN)
      : NaN;
    const amount = Number.isFinite(fromOrder)
      ? fromOrder
      : this._convertLocalToForeign(this.currentOrder?.get_total_with_tax?.() || this.currentOrder?.totalDue || 0);
    return this.env.utils.formatForeignCurrency(amount);
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

    let amounts = this.currentOrder.get_paymentlines().map((el) => el.amount)
    if (!amounts.every((el) => el != 0 && this.currentOrder.get_total_with_tax() !== 0)) {
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
