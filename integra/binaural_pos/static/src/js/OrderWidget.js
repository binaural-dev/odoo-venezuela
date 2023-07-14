odoo.define("binaural_pos.OrderWidget", function(require) {

  const OrderWidget = require("point_of_sale.OrderWidget")
  const Registries = require("point_of_sale.Registries")

  const BinauralOrderWidget = (OrderWidget) =>
    class BinauralOrderWidget extends OrderWidget {
      get rate_bcv() {
        let rate = this.env.pos.config.foreign_rate
        this.env.pos.get_order().get_orderlines().forEach(el =>{
          if(el.foreign_currency_rate != rate){
            rate = el.foreign_currency_rate
          }
        })
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

    }

  Registries.Component.extend(OrderWidget, BinauralOrderWidget)
  return OrderWidget

})
