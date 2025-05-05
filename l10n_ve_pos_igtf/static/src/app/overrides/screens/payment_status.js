/** @odoo-module */

import { PaymentScreenStatus } from "@point_of_sale/app/screens/payment_screen/payment_status/payment_status";
import { usePos } from "@point_of_sale/app/store/pos_hook";
import { patch } from "@web/core/utils/patch";
import {
  roundPrecision as round_pr,
} from "@web/core/utils/numbers";


// New orders are now associated with the current table, if any.
patch(PaymentScreenStatus.prototype, {
  setup() {
    super.setup(...arguments);
    this.pos = usePos();
  },
  get igtfAmount() {
    return this.env.utils.formatCurrency(this.props.order.get_igtf_amount(), 'Product Price')
  },
  get biAmount() {
    return this.env.utils.formatCurrency(this.props.order.get_bi_igtf(), 'Product Price')
  },
  get igtfForeignAmount() {
    return this.env.utils.formatForeignCurrency(this.props.order.get_foreign_igtf_amount(), 'Product Price')
  },
  get isIgtf() {
    let payment_lines = this.props.order.get_paymentlines();
    let is_igtf = false;
    payment_lines.forEach(function(payment_line) {
      if (payment_line.payment_method.apply_igtf) {
        is_igtf = true;
      }
    })
    return is_igtf;
  },
  get amountIGTF() {
    // Comprobamos si algún método de pago aplica IGTF
    let payment_lines = this.props.order.get_paymentlines();
    let hasIgtfMethod = false;
    payment_lines.forEach(payment_line => {
      if (payment_line.payment_method && payment_line.payment_method.apply_igtf) {
        hasIgtfMethod = true;
      }
    });
  
    // Si no hay métodos de pago que apliquen IGTF, devolvemos 0
    if (!hasIgtfMethod) {
      const igtfAmount = 0
      return this.env.utils.formatCurrency(igtfAmount, 'Product Price');
    }
  
    // Si hay un método de pago que aplica IGTF, realizamos el cálculo
    const totalWithTax = this.props.order.get_total_with_tax();
    const roundingApplied = this.props.order.get_rounding_applied();
    const igtfAmount = (totalWithTax * (this.pos.config.igtf_percentage / 100)) + roundingApplied;
    
    return this.env.utils.formatCurrency(igtfAmount, 'Product Price');
  },  
  get suggestedIgtf(){
      var rounding = this.pos.currency.rounding;
      var result = round_pr(this.props.order.get_total_with_tax() * (this.pos.config.igtf_percentage / 100),rounding);
      return this.env.utils.formatCurrency(result);
  },
  get displaySuggestedIgtf(){
    return this.pos.config.suggested_igtf
  },
  get foreignTotalDueTextWithIGTF() {
    return this.env.utils.formatForeignCurrency(
      (this.props.order.get_foreign_total_with_tax() * ((this.pos.config.igtf_percentage / 100) + 1)) + this.props.order.get_foreign_rounding_applied()
    );
  },
  get totalDueTextWithIGTF() {
    let payment_lines = this.props.order.get_paymentlines();


    if(payment_lines.length > 0){
      return this.env.utils.formatCurrency(
        (this.props.order.get_total_with_tax()));
    }else{
      return this.env.utils.formatCurrency(
        (this.props.order.get_total_without_igtf())
      );
    }
  },
  get totalDueTextWithIGTFDisplay() {
    var rounding = this.pos.currency.rounding;
    var result = round_pr(this.props.order.get_total_with_tax() * (this.pos.config.igtf_percentage / 100),rounding);
    return this.env.utils.formatCurrency(
      (this.props.order.get_total_with_tax()+result)
    );
  },
  get totalDueText() {
      return this.env.utils.formatCurrency(
          this.props.order.get_total_without_igtf()
      );
    },


})
