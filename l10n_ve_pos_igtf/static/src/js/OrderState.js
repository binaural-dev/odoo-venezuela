odoo.define("l10n_ve_pos_igtf.OrderState", function(require) {
  "use strict";

  const { Order, Payment } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");
  const utils = require("web.utils");

  var round_pr = utils.round_precision;

  const BinauralOrderState = (Order) =>
    class BinauralOrderState extends Order {
      constructor(obj, options) {
        super(...arguments);
        this.igtf_amount = 0;
        this.foreign_igtf_amount = 0;
        this.bi_igtf = 0;
        this.foreign_bi_igtf = 0;
      }
      init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.igtf_amount = json.igtf_amount;
        this.bi_igtf = json.bi_igtf;
        this.foreign_igtf_amount = json.foreign_igtf_amount;
        this.foreign_bi_igtf = json.foreign_bi_igtf;
      }
      export_as_JSON() {
        let json = super.export_as_JSON();
        json["igtf_amount"] = this.igtf_amount;
        json["bi_igtf"] = this.bi_igtf;
        json["foreign_igtf_amount"] = this.foreign_igtf_amount;
        json["foreign_bi_igtf"] = this.foreign_bi_igtf;
        return json;
      }
      update_igtf() {
        var rounding = this.pos.currency.rounding;
        const paymentlines = this.get_paymentlines();

        let last_igtf_amount = 0
        let last_foreign_igtf_amount = 0

        if (paymentlines.length > 0) {
          last_igtf_amount = this.igtf_amount
          last_foreign_igtf_amount = this.foreign_igtf_amount
        }

        let is_return = this.get_total_without_igtf() < 0

        this.igtf_amount = 0;
        this.foreign_igtf_amount = 0;
        this.bi_igtf = 0;
        this.foreign_bi_igtf = 0

        let bi_igtf = 0;
        let foreign_bi_igtf = 0;
        let repeat_same_method = [];
        let bi_payments = [];

        let igtf_amount = 0
        let foreign_igtf_amount = 0

        paymentlines.forEach((payment) => {
          payment.set_include_igtf(false)
        })

        if (this.to_receipt) {
          return
        }

        paymentlines.forEach((payment) => {
          let is_change = false
          if (!is_return) {
            is_change = payment.amount < 0
          } else {
            is_change = payment.amount > 0
          }

          if (payment.payment_method.apply_igtf && last_igtf_amount == payment.amount) {
            return
          }

          if (!payment.payment_method.apply_igtf) {
            return;
          }



          bi_igtf += round_pr(payment.amount, rounding);
          foreign_bi_igtf += round_pr(payment.get_foreign_amount(), rounding);
          repeat_same_method.push(payment.payment_method.id)
          bi_payments.push(payment.cid)


          payment.set_include_igtf(true)

          let amount_to_pay = payment.amount
          let foreign_amount_to_pay = payment.get_foreign_amount()

          if (payment.amount > this.get_total_with_tax() && !is_return || payment.amount < this.get_total_with_tax() && is_return) {
            amount_to_pay = this.get_total_with_tax()
            foreign_amount_to_pay = this.get_foreign_total_with_tax()
          }

          if (!is_change) {
            payment.set_igtf_amount(this.compute_igtf_amount(amount_to_pay))
            payment.set_foreign_igtf_amount(this.compute_igtf_amount(foreign_amount_to_pay))

            igtf_amount += payment.igtf_amount
            foreign_igtf_amount += payment.foreign_igtf_amount
          }
          else{
            payment.set_include_igtf(false)
          }
        })

        if (bi_igtf !== 0 && ((bi_igtf >= this.get_total_without_igtf() && !is_return) || (bi_igtf <= this.get_total_without_igtf() && is_return))) {
          bi_igtf = this.get_total_without_igtf()
          foreign_bi_igtf = this.get_foreign_total_without_igtf()
          igtf_amount = this.compute_igtf_amount(bi_igtf)
          foreign_igtf_amount = this.compute_igtf_amount(foreign_bi_igtf)

          let payment_without_change = paymentlines.filter((payment) => {
            if(!bi_payments.includes(payment.cid)){
              return false
            }

            let is_change = false
            if (!is_return) {
              is_change = payment.amount < 0
            } else {
              is_change = payment.amount > 0
            }

            if (is_change) {
              return false
            }

            return true

          })

          if (payment_without_change.length > 0) {
            payment_without_change.forEach((payment) => {
              if (!payment.include_igtf) {
                return
              }
              payment.set_igtf_amount(igtf_amount / payment_without_change.length)
              payment.set_foreign_igtf_amount(foreign_igtf_amount / payment_without_change.length)
            })
          }
        }

        this.bi_igtf = bi_igtf;
        this.foreign_bi_igtf = foreign_bi_igtf;

        this.igtf_amount = igtf_amount;
        this.foreign_igtf_amount = foreign_igtf_amount;


        return this.igtf_amount;
      }
      compute_igtf_amount(amount) {
        var rounding = this.pos.currency.rounding;
        return round_pr(amount * (this.pos.config.igtf_percentage / 100), rounding);
      }
      get_igtf_amount() {
        return this.igtf_amount;
      }
      get_foreign_igtf_amount() {
        return this.foreign_igtf_amount;
      }
      get_bi_igtf() {
        return this.bi_igtf;
      }
      add_paymentline(payment_method) {

        let is_change = false
        let is_return = this.get_total_without_igtf() < 0
        if (!is_return) {
          is_change = this.get_due() < 0
        } else {
          is_change = this.get_due() > 0
        }

        if (!this.to_receipt
          && !payment_method.apply_igtf
          || this.get_due() <= this.get_igtf_amount()
          || is_change) {
          let res = super.add_paymentline(...arguments);
          this.update_igtf()
          return res;
        }
        let res_igtf = this.add_paymentline_without_igtf(...arguments)
        this.update_igtf()
        return res_igtf
      }
      add_paymentline_without_igtf(payment_method) {
        this.assert_editable();
        if (this.electronic_payment_in_progress()) {
          return false;
        } else {
          var newPaymentline = Payment.create({}, { order: this, payment_method: payment_method, pos: this.pos });
          this.paymentlines.add(newPaymentline);
          this.select_paymentline(newPaymentline);
          if (this.pos.config.cash_rounding) {
            this.selected_paymentline.set_amount(0);
          }

          newPaymentline.set_foreign_amount(this.get_foreign_due() - this.get_foreign_igtf_amount())
          newPaymentline.set_amount(
            this.get_due() - this.get_igtf_amount()
          );

          if (payment_method.payment_terminal) {
            newPaymentline.set_payment_status('pending');
          }
          return newPaymentline;
        }
      }
      remove_paymentline(line) {
        const res = super.remove_paymentline(...arguments);
        this.update_igtf()
        return res
      }
      get_total_without_igtf() {
        const res = super.get_total_with_tax(...arguments);
        return res
      }
      get_foreign_total_without_igtf() {
        const res = super.get_foreign_total_with_tax(...arguments);
        return res
      }
      get_total_with_tax() {
        const res = super.get_total_with_tax(...arguments);
        return res + this.igtf_amount;
      }
      get_foreign_total_with_tax() {
        return super.get_foreign_total_with_tax(...arguments) + this.foreign_igtf_amount
      }
      get_max_total_with_igtf() {
        return this.compute_igtf_amount(super.get_foreign_total_with_tax()) + this.props.order.get_foreign_rounding_applied()
      }
    };
  Registries.Model.extend(Order, BinauralOrderState);
  return BinauralOrderState;
})
