odoo.define("binaural_pos.OrderState", function(require) {
  "use strict";

  const { Order, Payment } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");
  const utils = require("web.utils");

  var round_pr = utils.round_precision;

  const BinauralOrderState = (Order) =>
    class BinauralOrderState extends Order {
      constructor(data, opt) {
        super(...arguments);
        this.to_invoice = true;
        let always_invoice = !this.pos.config.always_invoice;
        this.to_receipt = always_invoice;
        this.toggle_receipt_invoice(always_invoice)
      }
      get is_refund() {
        return Object.values(this.pos.toRefundLines).length != 0
      }
      get current_rate() {
        let rate = this.pos.config.foreign_rate
        if (Object.values(this.pos.toRefundLines).length == 0) {
          return rate
        }
        Object.values(this.pos.toRefundLines).forEach(el => {
          if (el.orderline.foreign_currency_rate != rate) {
            rate = el.orderline.foreign_currency_rate
          }
        })
        return rate
      }
      init_from_JSON(json) {
        super.init_from_JSON(...arguments)
        this.to_receipt = json["to_receipt"]
        this.to_invoice = true;
        this.foreign_currency_rate = json.foreign_currency_rate || this.pos.config.foreign_rate
      }

      set_orderline_options(orderline, options) {
        super.set_orderline_options(orderline, options)

        if (options.foreign_currency_rate !== undefined) {
          orderline.set_foreign_currency_rate(options.foreign_currency_rate);
        }
        if (options.foreign_price !== undefined) {
          orderline.set_foreign_price(options.foreign_price);
        }
      }
      add_orderline(line) {
        super.add_orderline(...arguments)
        this.toggle_receipt_invoice(this.to_receipt)
      }
      export_as_JSON() {
        let json = super.export_as_JSON();
        json["foreign_amount_total"] = this.get_foreign_total_with_tax();
        json["foreign_currency_rate"] = this.foreign_currency_rate || this.pos.config.foreign_rate;
        json["to_receipt"] = this.is_to_receipt();
        return json;
      }
      onchage_receipt(to_receipt) {
        if (this.pos.config.pos_tax_inside) return

        if (to_receipt == undefined) {
          return
        }
        if (to_receipt) {
          const taxes = Object.values(this.pos.taxes_by_id)
          const exempt = taxes.find(el => el.amount == 0 && el.type_tax_use == "sale")
          this.orderlines.forEach((el) => {
            el.product.taxes_id = [exempt.id]
            el.tax_ids = el.product.taxes_id
          })
        } else {
          this.orderlines.forEach((el) => {
            el.product.taxes_id = el.product.originalTaxes
            el.tax_ids = el.product.taxes_id
          })
        }
      }
      toggle_receipt_invoice(to_receipt) {
        this.assert_editable();
        this.to_receipt = to_receipt;
        this.onchage_receipt(to_receipt)
      }
      is_to_receipt() {
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
        return round_pr(this.paymentlines.reduce(((sum, paymentLine) => {
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

      calculate_foreign_base_amount(tax_ids_array, lines) {
        // Consider price_include taxes use case
        let has_taxes_included_in_price = tax_ids_array.filter(tax_id =>
          this.pos.taxes_by_id[tax_id].price_include
        ).length;

        let base_amount = lines.reduce((sum, line) =>
          sum +
          line.get_foreign_price_without_tax() +
          (has_taxes_included_in_price ? line.get_foreign_total_taxes_included_in_price() : 0),
          0
        );
        return base_amount;
      }
    };
  Registries.Model.extend(Order, BinauralOrderState);
  return BinauralOrderState;
})
