odoo.define("l10n_ve_pos.PaymentScreenStatus", function (require) {
  const PaymentScreenStatus = require("point_of_sale.PaymentScreenStatus");
  const Registries = require("point_of_sale.Registries");

  const BinauralPaymentScreenStatus = (PaymentScreenStatus) =>
    class BinauralPaymentScreenStatus extends PaymentScreenStatus {
      get foreignChangeText() {
        return this.env.pos.format_foreign_currency(
          this.props.order.get_foreign_change()
        );
      }
      get foreignTotalDueText() {
        return this.env.pos.format_foreign_currency(
          this.props.order.get_foreign_total_with_tax() +
            this.props.order.get_foreign_rounding_applied()
        );
      }
      get foreignRemainingText() {
        return this.env.pos.format_foreign_currency(
          this.props.order.get_due() > 0
            ? this.props.order.get_foreign_due()
            : 0
        );
      }
      get rate_bcv() {
        let rate = this.env.pos.get_order().current_rate
        let amount = this.env.pos.format_currency_no_symbol(
          rate,
          "Product Price",
          {
            id: 2,
            name: "USD",
            symbol: "$",
            position: "before",
            rounding: 0.01,
            rate: 1,
            decimal_places: 2,
          }
        );
        return `$ ${amount}`;
      }
    };

  Registries.Component.extend(PaymentScreenStatus, BinauralPaymentScreenStatus);
  return PaymentScreenStatus;
});
