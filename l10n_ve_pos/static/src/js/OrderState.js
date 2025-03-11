odoo.define("l10n_ve_pos.OrderState", function(require) {
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
      }
      get_qty_products(){
        let qty = 0
        this.get_orderlines().forEach((line) => {
          qty += line.quantity
        })
        return qty
      }
      get_orderlines() {
        if (!this.cid || !this.pos.get_order()) {
          return this.orderlines
        }

        if (this.cid != this.pos.get_order().cid) {
          return this.orderlines;
        }

        if (this.orderlines.length < 1) {
          return this.orderlines
        }

        let line = this.orderlines[0]

        if (!line.refunded_orderline_id) {
          return this.orderlines
        }

        return this.orderlines;
      }
      get is_refund(){
        return this.getHasRefundLines()
      }
      get config_rate(){
	//FIXME Buscar una manera de esto sea por id y no por name
        if(this.pos.currency.name == "VEF"){
        return this.pos.config.foreign_inverse_rate
        }
        if(this.pos.currency.name == "USD"){
        return this.pos.config.foreign_rate
        }
      }
      get rate_from_lines(){
        let rate = this.config_rate 
        if (!this.is_refund){
          return rate
        }
        Object.values(this.pos.toRefundLines).forEach(el => {
          if (el.orderline.foreign_currency_rate != rate) {
            rate = el.orderline.foreign_currency_rate
          }
        })
        return rate
      }
      get current_rate() {
        let rate = this.rate_from_lines
        this.set_foreign_currency_rate(rate)
        return rate
      }
      get display_current_rate () {
        return this.pos.config.foreign_rate;
      }
      set_foreign_currency_rate(rate) {
        this.foreign_currency_rate = rate;
      }
      init_from_JSON(json) {
        super.init_from_JSON(...arguments)
        this.to_invoice = true;
        //TODO: Check how I can change this to make it change according to the currency of the company..
        this.foreign_currency_rate =json.foreign_currency_rate || this.pos.config.foreign_inverse_rate 
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
      export_as_JSON() {
        let json = super.export_as_JSON();
        json["foreign_amount_total"] = this.get_foreign_total_with_tax();
        json["foreign_currency_rate"] = this.foreign_currency_rate || this.pos.config.foreign_rate;
        return json;
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
