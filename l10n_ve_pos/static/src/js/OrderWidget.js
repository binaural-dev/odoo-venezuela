odoo.define("l10n_ve_pos.OrderWidget", function(require) {

  const OrderWidget = require("point_of_sale.OrderWidget")
  const Registries = require("point_of_sale.Registries")

  const BinauralOrderWidget = (OrderWidget) =>
    class BinauralOrderWidget extends OrderWidget {
      get rate_bcv() {

        let rate = this.env.pos.get_order().get_selected_orderline().get_orderline_rate_from_orderline();
        let amount = this.env.pos.format_currency_no_symbol(
          rate,
          "Product Price",
          {
            "id": 2,
            "name": "USD",
            "symbol": "$",
            "position": "before",
            "rounding": 0.01,
            "rate": 1,
            "decimal_places": 2
          }
        );
        return `$ ${amount}`
      }

      get product_qty() {
        return this.env.pos.get_order().get_qty_products()
      }

    }

  Registries.Component.extend(OrderWidget, BinauralOrderWidget)
  return OrderWidget

})
