odoo.define('binaural_pos_sale.PosSaleProductConfiguratorOrder', function (require) {
  "use strict";

  var { Order } = require('point_of_sale.models');
  const Registries = require('point_of_sale.Registries');

  // Inherit from addons/pos_sale_product_configurator/static/src/js/models.js
  const PosSaleProductConfiguratorOrder = (Order) => class PosSaleProductConfiguratorOrder extends Order {
      async add_product(product, options) {
          super.add_product(...arguments);
      }
  }
  Registries.Model.extend(Order, PosSaleProductConfiguratorOrder);
})
