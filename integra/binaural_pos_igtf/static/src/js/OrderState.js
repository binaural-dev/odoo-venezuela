odoo.define("binaural_pos_igtf.OrderState", function(require) {
  "use strict";

  const { Order } = require("point_of_sale.models");
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
        if (this.to_receipt) {
          return
        }
        var rounding = this.pos.currency.rounding;
        const paymentlines = this.get_paymentlines();

        let last_igtf_amount = this.igtf_amount

        this.igtf_amount = 0;
        this.foreign_igtf_amount = 0;
        this.bi_igtf = 0;
        this.foreign_bi_igtf = 0

        let bi_igtf = 0;
        let foreign_bi_igtf = 0;
        let repeat_same_method = [];
        let bi_payments = [];

        let has_change = false

        paymentlines.forEach((payment) => {
          if (payment.is_change) {
            has_change = true
          }
          if (!payment.payment_method.apply_igtf
            || repeat_same_method.includes(payment.payment_method.id) || payment.is_change) {
            return;
          }

          if (payment.payment_method.apply_igtf && last_igtf_amount == payment.amount) {
            return
          }

          bi_igtf += round_pr(payment.amount, rounding);
          foreign_bi_igtf += round_pr(payment.get_foreign_amount(), rounding);
          repeat_same_method.push(payment.payment_method.id)
          bi_payments.push(payment.cid)
        })

        if (bi_igtf > this.get_total_without_igtf()) {
          bi_igtf = this.get_total_without_igtf()
          foreign_bi_igtf = this.get_foreign_total_without_igtf()
        }

        if (bi_igtf !== 0) {
          this.igtf_amount = this.compute_igtf_amount(bi_igtf)
          this.foreign_igtf_amount = this.compute_igtf_amount(foreign_bi_igtf);
          this.bi_igtf = bi_igtf;
          this.foreign_bi_igtf = foreign_bi_igtf;
        }


        paymentlines.forEach((el) => {
          el.set_include_igtf(false)
          if (this.igtf_amount <= el.amount && !el.is_change && !bi_payments.includes(el.cid)) {
            el.set_include_igtf(true)
          }
        })

        if (
          bi_payments.length == 1
          && paymentlines.filter((el) => bi_payments[0] == el.cid)[0].amount > this.get_total_with_tax()
        ) {
          paymentlines.filter((el) => bi_payments[0] == el.cid)[0].set_include_igtf(true)
        }

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
      add_paymentline(payment_method) {
        const res = super.add_paymentline(...arguments);
        this.update_igtf()
        return res;
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
