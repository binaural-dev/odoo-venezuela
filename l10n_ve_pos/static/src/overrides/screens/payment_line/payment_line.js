
import { PaymentScreenPaymentLines } from "@point_of_sale/app/screens/payment_screen/payment_lines/payment_lines";
import { patch } from "@web/core/utils/patch";

// New orders are now associated with the current table, if any.
patch(PaymentScreenPaymentLines.prototype, {

  formatLineAmount(paymentline) {
    
    console.log("paymentline selected", paymentline.isSelected()) 
    const selectedPaymentId = this.pos.selectedOrder.payment_ids.find(payment => payment.id === paymentline.id)
    
    if (!selectedPaymentId) {
      return this.env.utils.formatForeignCurrency(paymentline.amount / this.pos.config.foreign_rate)
    }

    console.log("selectedPaymentId", selectedPaymentId.id)  
    return this.env.utils.formatForeignCurrency(paymentline.amount / this.pos.config.foreign_rate)
      
  },
})