odoo.define("binaural_pos.OrderState", function(require) {
  "use strict";

  const { Order, Payment } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");
  const utils = require("web.utils");

  var round_pr = utils.round_precision;

  const BinauralOrderState = (Order) =>
    class BinauralOrderState extends Order {
      constructor() {
        super(...arguments);
        this.to_invoice = true;
        let always_invoice = !this.pos.config.always_invoice;
        this.to_receipt = always_invoice;
      }
      export_as_JSON() {
        let json = super.export_as_JSON();
        json["foreign_amount_total"] = this.get_foreign_total_with_tax()
        json["foreign_currency_rate"] = this.pos.config.foreign_rate
        json["to_receipt"] = this.is_to_receipt()
        return json;
      }
      toggle_receipt_invoice(to_receipt) {
        this.assert_editable();
        this.to_receipt = to_receipt;
      }
      is_to_receipt() {
        console.log(this)
        return this.to_receipt;
      }
      add_paymentline(payment_method) {
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

          newPaymentline.set_foreign_amount(this.get_foreign_due())
          newPaymentline.set_amount(
            this.get_due()
          );

          if (payment_method.payment_terminal) {
            newPaymentline.set_payment_status('pending');
          }
          return newPaymentline;
        }
      }
      get_foreign_total_tax() {
        if (this.pos.company.tax_calculation_rounding_method === "round_globally") {
          // As always, we need:
          // 1. For each tax, sum their amount across all order lines
          // 2. Round that result
          // 3. Sum all those rounded amounts
          var groupTaxes = {};
          this.orderlines.forEach(function(line) {
            var taxDetails = line.get_foreign_tax_details();
            var taxIds = Object.keys(taxDetails);
            for (var t = 0; t < taxIds.length; t++) {
              var taxId = taxIds[t];
              if (!(taxId in groupTaxes)) {
                groupTaxes[taxId] = 0;
              }
              groupTaxes[taxId] += taxDetails[taxId];
            }
          });

          var sum = 0;
          var taxIds = Object.keys(groupTaxes);
          for (var j = 0; j < taxIds.length; j++) {
            var taxAmount = groupTaxes[taxIds[j]];
            sum += round_pr(taxAmount, this.pos.foreign_currency.rounding);
          }
          return sum;
        } else {
          return round_pr(this.orderlines.reduce((function(sum, orderLine) {
            return sum + orderLine.get_foreign_tax();
          }), 0), this.pos.foreign_currency.rounding);
        }
      }
      get_foreign_total_without_tax() {
        return round_pr(this.orderlines.reduce((function(sum, orderLine) {
          return sum + orderLine.get_foreign_price_without_tax();
        }), 0), this.pos.foreign_currency.rounding);
      }
      get_foreign_total_with_tax() {
        return this.get_foreign_total_without_tax() + this.get_foreign_total_tax();
      }
      get_foreign_total_paid() {
        return round_pr(this.paymentlines.reduce((function(sum, paymentLine) {
          if (paymentLine.is_done()) {
            sum += paymentLine.get_foreign_amount();
          }
          return sum;
        }), 0), this.pos.foreign_currency.rounding);
      }
      get_foreign_change(paymentline) {
        if (!paymentline) {
          var change = this.get_foreign_total_paid() - this.get_foreign_total_with_tax() - this.get_foreign_rounding_applied();
        } else {
          var change = -this.get_foreign_total_with_tax();
          var lines = this.paymentlines;
          for (var i = 0; i < lines.length; i++) {
            change += lines[i].get_foreign_amount();
            if (lines[i] === paymentline) {
              break;
            }
          }
        }
        return round_pr(Math.max(0, change), this.pos.currency.rounding);
      }
      get_foreign_due(paymentline) {
        try {

          if (!paymentline) {
            var due = this.get_foreign_total_with_tax() - this.get_foreign_total_paid() + this.get_foreign_rounding_applied();
          } else {
            var due = this.get_foreign_total_with_tax();
            var lines = this.paymentlines;
            for (var i = 0; i < lines.length; i++) {
              if (lines[i] === paymentline) {
                break;
              } else {
                due -= lines[i].get_foreign_amount();
              }
            }
          }
          return round_pr(due, this.pos.foreign_currency.rounding);
        } catch (err) {
          console.log(err);

          return round_pr(4, this.pos.foreign_currency.rounding);
        }
      }
      get_foreign_rounding_applied() {
        if (this.pos.config.cash_rounding) {
          const only_cash = this.pos.config.only_round_cash_method;
          const paymentlines = this.get_paymentlines();
          const last_line = paymentlines ? paymentlines[paymentlines.length - 1] : false;
          const last_line_is_cash = last_line ? last_line.payment_method.is_cash_count == true : false;
          if (!only_cash || (only_cash && last_line_is_cash)) {
            var rounding_method = this.pos.cash_rounding[0].rounding_method;
            var remaining = this.get_foreign_total_with_tax() - this.get_foreign_total_paid();
            var sign = this.get_foreign_total_with_tax() > 0 ? 1.0 : -1.0;
            if (this.get_foreign_total_with_tax() < 0 && remaining > 0 || this.get_foreign_total_with_tax() > 0 && remaining < 0) {
              rounding_method = rounding_method.endsWith("UP") ? "DOWN" : rounding_method;
            }

            remaining *= sign;
            var total = round_pr(remaining, this.pos.cash_rounding[0].rounding);
            var rounding_applied = total - remaining;

            // because floor and ceil doesn't include decimals in calculation, we reuse the value of the half-up and adapt it.
            if (utils.float_is_zero(rounding_applied, this.pos.foreign_currency.decimal_places)) {
              // https://xkcd.com/217/
              return 0;
            } else if (Math.abs(this.get_foreign_total_with_tax()) < this.pos.cash_rounding[0].rounding) {
              return 0;
            } else if (rounding_method === "UP" && rounding_applied < 0 && remaining > 0) {
              rounding_applied += this.pos.cash_rounding[0].rounding;
            }
            else if (rounding_method === "UP" && rounding_applied > 0 && remaining < 0) {
              rounding_applied -= this.pos.cash_rounding[0].rounding;
            }
            else if (rounding_method === "DOWN" && rounding_applied > 0 && remaining > 0) {
              rounding_applied -= this.pos.cash_rounding[0].rounding;
            }
            else if (rounding_method === "DOWN" && rounding_applied < 0 && remaining < 0) {
              rounding_applied += this.pos.cash_rounding[0].rounding;
            }
            return sign * rounding_applied;
          }
          else {
            return 0;
          }
        }
        return 0;
      }
    };
  Registries.Model.extend(Order, BinauralOrderState);
  return BinauralOrderState;
})
