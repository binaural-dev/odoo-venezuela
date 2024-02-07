odoo.define("binaural_scale.OrderlineState", function(require) {
  "use strict";

  const { Order } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");

  const BinauralOrder = (Order) =>
    class BinauralOrder extends Order {
      set_orderline_options(orderline, options) {
        let res = super.set_orderline_options(orderline, options)

        if (
          options.price !== undefined 
          && !!orderline.product.plu_id 
          && this.pos.config.scan_barcode_scale_by_price_with_tax
        ) {
          let taxes_ids = orderline.product.taxes_id;
          taxes_ids = _.filter(taxes_ids, t => t in this.pos.taxes_by_id);
          let product_taxes = this.pos.get_taxes_after_fp(taxes_ids, this.fiscal_position);

          let new_taxes = JSON.parse(JSON.stringify(product_taxes));
          new_taxes.forEach(line => {
            line.price_include = true
          })

          const price_without_taxes = this.pos.compute_all(
            new_taxes,
            options.price,
            1,
            this.pos.currency.rounding,
            true)
            .total_excluded

          orderline.set_unit_price(price_without_taxes);
          this.fix_tax_included_price(orderline);
        }
        return res
      }
    }
  Registries.Model.extend(Order, BinauralOrder);
})
