odoo.define("l10n_ve_pos.ProductState", function(require) {
  "use strict";

  const { Product } = require("point_of_sale.models");
  const Registries = require("point_of_sale.Registries");

  const BinauralProductState = (Product) =>
    class BinauralProductState extends Product {
      constructor(obj) {
        super(...arguments)
        this.originalTaxes = this.taxes_id
      }

    };
  Registries.Model.extend(Product, BinauralProductState);
  return BinauralProductState
})
