odoo.define("binaural_pos_igtf.PaymentScreenPaymentLine", function(require) {

  const PaymentScreenPaymentLine = require("point_of_sale.PaymentScreenPaymentLines")
  const Registries = require("point_of_sale.Registries")
  const { _t } = require('web.core');

  const BinauralPaymentScreenPaymentLine = (PaymentScreenPaymentLine) =>
    class BinauralPaymentScreenPaymentLine extends PaymentScreenPaymentLine {
      formatIgtfAmount(paymentline){
        return this.env.pos.format_currency_no_symbol(paymentline.igtf_amount)
      }
    }

  Registries.Component.extend(PaymentScreenPaymentLine, BinauralPaymentScreenPaymentLine)
  return PaymentScreenPaymentLine 
})
