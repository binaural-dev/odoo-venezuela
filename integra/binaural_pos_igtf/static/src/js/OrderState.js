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
        var rounding = this.pos.currency.rounding;
        const paymentlines = this.get_paymentlines();

        this.igtf_amount = 0;
        this.foreign_igtf_amount = 0;
        this.bi_igtf = 0;
        this.foreign_bi_igtf = 0

        let bi_igtf = 0;
        let foreign_bi_igtf = 0;
        let repeat_payments = [];

        let igtf_limit = this.get_total_with_tax() * (this.pos.config.igtf_percentage / 100);
        let foreign_igtf_limit = this.get_foreign_total_with_tax() * (this.pos.config.igtf_percentage / 100);

        paymentlines.forEach((payment) => {
          if (!payment.payment_method.apply_igtf
            || repeat_payments.includes(payment.payment_method.id)) {
            return;
          }
          bi_igtf += round_pr(payment.amount, rounding);
          foreign_bi_igtf += round_pr(payment.foreign_amount, rounding);
          repeat_payments.push(payment.payment_method.id)
        })
        if (bi_igtf !== 0) {

          this.igtf_amount = round_pr(bi_igtf * (this.pos.config.igtf_percentage / 100), rounding);
          this.foreign_igtf_amount = round_pr(foreign_bi_igtf * (this.pos.config.igtf_percentage / 100), rounding);
          this.bi_igtf = bi_igtf;
          this.foreign_bi_igtf = foreign_bi_igtf;
        }

        if (this.igtf_amount > igtf_limit) {
          this.igtf_amount = igtf_limit;
          this.foreign_igtf_amount = foreign_igtf_limit;
        }
        return this.igtf_amount;
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
        const res = super.get_total_without_tax(...arguments);
        return res
      }
      get_total_without_tax() {
        const res = super.get_total_without_tax(...arguments);
        return res + this.igtf_amount;
      }
      get_foreign_total_without_tax() {
        return super.get_foreign_total_without_tax(...arguments) + this.foreign_igtf_amount
      }
    };
  Registries.Model.extend(Order, BinauralOrderState);
  return BinauralOrderState;
})
