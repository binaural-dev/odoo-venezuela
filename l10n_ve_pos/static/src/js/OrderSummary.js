odoo.define("l10n_ve_pos.OrderSummary", function(require) {
  "use strict";

  const OrderSummary = require("point_of_sale.OrderSummary");
  const Registries = require("point_of_sale.Registries");
  const { float_is_zero } = require('web.utils');

  const BinauralOrderSummary = (Orderline) =>
    class BinauralOrderSummary extends Orderline {
      getForeignTotal() {
        return this.env.pos.format_foreign_currency(this.props.order.get_foreign_total_with_tax());
      }
      getForeignTax() {
        try {
          const total = this.props.order.get_foreign_total_with_tax();
          const totalWithoutTax = this.props.order.get_foreign_total_without_tax();
          const taxAmount = total - totalWithoutTax;
          return {
            hasTax: !float_is_zero(taxAmount, this.env.pos.foreign_currency.decimal_places),
            displayAmount: this.env.pos.format_foreign_currency(taxAmount),
          };
        } catch (e) {
          return this.getTax()
        }
      }
      getTax() {
        let res = super.getTax(...arguments)
        if(this.env.pos.config.pos_tax_inside){
          res["hasTax"] = false
        }
        return res 
      }
    }

  Registries.Component.extend(OrderSummary, BinauralOrderSummary);
  return BinauralOrderSummary;
})
