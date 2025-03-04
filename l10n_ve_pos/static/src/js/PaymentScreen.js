odoo.define("l10n_ve_pos.PaymentScreen", function (require) {
  const PaymentScreen = require("point_of_sale.PaymentScreen");
  const Registries = require("point_of_sale.Registries");
  const NumberBuffer = require("point_of_sale.NumberBuffer");

  const BinauralPaymentScreen = (PaymentScreen) =>
    class BinauralPaymentScreen extends PaymentScreen {
      addNewPaymentLine({ detail: paymentMethod }) {
        if(paymentMethod["type"] == "cash"){
          this.env.pos.open_cashbox();
        }
        return super.addNewPaymentLine(...arguments);
      }

      shouldDownloadInvoice() {
          return false;
      }
      _updateSelectedPaymentline() {
        // do nothing if there is not a selected payment line
        if (!this.selectedPaymentLine) return;

        if (!this.selectedPaymentLine.payment_method.is_foreign_currency) {
          let res = super._updateSelectedPaymentline()
          if (!!this.selectedPaymentLine) {
            this.selectedPaymentLine
              .set_foreign_amount(NumberBuffer.getFloat() * this.env.pos.config.foreign_rate)
          }
          return res;
        }

        if (NumberBuffer.get() === null) {
          this.deletePaymentLine({
            detail: { cid: this.selectedPaymentLine.cid },
          });
        } else {
          this.selectedPaymentLine.set_foreign_amount(NumberBuffer.getFloat());
          this.selectedPaymentLine.set_amount(
            NumberBuffer.getFloat() *
              this.env.pos.foreign_currency["inverse_rate"]
          );
        }
      }

      async _isOrderValid(isForceValidate) {
        let res = await super._isOrderValid(isForceValidate)
        if (!this.currentOrder) {
          return res
        }

        let amounts = this.currentOrder.get_paymentlines().map((el) => el.amount)
        if (!amounts.every((el) => el != 0)) {
          this.showPopup('ErrorPopup', {
            title: this.env._t('Empty Paymentline'),
            body: this.env._t(
              "You can't validate with empty payment lines"
            ),
          });
          return false

        }
        return res
      }

      async showPaymentsOrigin() {

        let id = []
        if (Object.values(this.env.pos.toRefundLines).length == 0) {
          return
        }
        Object.values(this.env.pos.toRefundLines).forEach(el => {
          id = el.orderline.orderBackendId
        })
        let payments = await this.rpc({
          model: 'pos.order',
          method: 'get_payments_order_refund',
          args: [id],
          kwargs: {},
        });

        let payment_list = payments.map(el => {
          return {
          id: el.id,
          label: el.payment_method_id[1] + " " + el.display_name,
          isSelected: false,
          item: el,
        }

        })
        this.showPopup("SelectionPopup", {
          title: this.env._t("Payments"),
          list: payment_list,
        });
      }

      get isChangeZero() {
        return this.currentOrder.get_change() === 0;
      }
    };

  Registries.Component.extend(PaymentScreen, BinauralPaymentScreen);
  return PaymentScreen;
});
