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

  get foreignTotalDueText() {
    return this.utils.formatForeignCurrency(this.currentOrder.get_foreign_total_with_tax())
  },

  shouldDownloadInvoice() {
    return false;
  },

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
  
  updateSelectedPaymentline(amount = false) {
    return super.updateSelectedPaymentline(amount);

  },
  
  async validateOrder(isForceValidate) {
    const order = this.currentOrder || this.pos.get_order();
    const selectedLine =
      order?.getSelectedPaymentline?.() ||
      order?.selected_paymentline ||
      null;

    if (selectedLine) {
      console.log(
        "Selected Amount:",
        selectedLine.amount ?? selectedLine.get_amount?.() ?? 0,
      );

      console.log(
        "Payment Method:",
        selectedLine.payment_method_id?.name ||
          selectedLine.payment_method?.name ||
          "",
      );
    }

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
