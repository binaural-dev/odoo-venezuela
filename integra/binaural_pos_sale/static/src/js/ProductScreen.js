odoo.define('binaural_pos_sale.ProductScreen', function(require) {
  "use strict";

  const Registries = require('point_of_sale.Registries');
  const ProductScreen = require('point_of_sale.ProductScreen');
  const { _t } = require("web.core");

  const BinauralProductScreen = (ProductScreen) =>
    class BinauralProductScreen extends ProductScreen {
      async _onClickPay() {
        const order = this.env.pos.get_order();
        const orderlines = order.get_orderlines();

        let ids = []

        orderlines.forEach(line => {
          if (line.sale_order_line_id !== undefined) {
            ids.push(line.sale_order_line_id.id)
          }
        })

        if (ids.length === 0) {
          return super._onClickPay();
        }

        let data = await this.env.services.rpc({
          model: 'sale.order.line',
          method: 'search_read',
          args: [[['id', 'in', ids]], ['name']],
        });
        if (data.length != ids.length) {
          return this.showPopup('ErrorPopup', {
            title: _t('Order error'),
            body: _t('This order has been modified. Please refresh the order.')
          });
        }

        return super._onClickPay();
      }
    };

  Registries.Component.extend(ProductScreen, BinauralProductScreen);

  return BinauralProductScreen;

});
