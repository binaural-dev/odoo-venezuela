odoo.define("l10n_ve_pos.PaymentScreenPaymentLine", function(require) {

  const PaymentScreenPaymentLine = require("point_of_sale.PaymentScreenPaymentLines")
  const Registries = require("point_of_sale.Registries")
  const { _t } = require('web.core');

  const BinauralPaymentScreenPaymentLine = (PaymentScreenPaymentLine) =>
    class BinauralPaymentScreenPaymentLine extends PaymentScreenPaymentLine {
      formatLineAmount(paymentline){
        if (paymentline.payment_method.is_foreign_currency) {
          return this.env.pos.format_currency_no_symbol(paymentline.get_foreign_amount())
        }
        return super.formatLineAmount(paymentline)
      }

    }

  Registries.Component.extend(PaymentScreenPaymentLine, BinauralPaymentScreenPaymentLine)
  return PaymentScreenPaymentLine 
})
